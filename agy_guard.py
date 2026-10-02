#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agy 網路守門員 —— 共用給 shim 與 agy_meter。

要解決的問題：在某些網路（例如會擋 Google 服務的學校校內網路），agy 連不上但仍會嘗試登入／刷新 token，
**失敗的刷新會弄壞 ~/.gemini/jetski-standalone-oauth-token**，回家後要重新登入。

為什麼不用寫死網段：同一個場域常有好幾個網段，有的會失敗、有的一時正常。猜網段一定會漏，
而漏掉的代價就是又一次壞掉的登入。

地點相關的設定（要封鎖的 DNS 網域、選單列顯示用的區域）放在本機的
~/.gemini/agy-guard/zones.json，不進 repo；格式見 zones.example.json。

改成**自己學**：
  - 指紋 = 閘道 MAC + /24 網段（閘道 MAC 對每個 VLAN 是穩定且唯一的）
  - 任何一次因網路/認證失敗的呼叫，把當下指紋寫進黑名單
  - 之後在同一個網路直接拒絕，連二進位檔都不啟動 → 不會碰到 token
  - 每次成功呼叫都備份 token；偵測到壞掉就還原
"""
import json, os, re, shutil, socket, subprocess, sys, time
from pathlib import Path

GUARD = Path.home() / ".gemini" / "agy-guard"
BLOCK = GUARD / "blocklist.json"
ZONES_FILE = GUARD / "zones.json"   # 本機地點設定，不進 repo（範例：zones.example.json）
TOKBK = GUARD / "token.backup"
TOKEN = Path.home() / ".gemini" / "jetski-standalone-oauth-token"
AUTO_BLOCK_AFTER = 2   # 自動記錄的網路失敗幾次才封鎖（一次多半是暫時性的）
INCIDENT_WINDOW = 60   # 秒：距上次失敗不到這麼久的，視為同一次事件（內建重試不重複計數）
# 認定「這次失敗是網路/認證造成」的訊號
FAIL_PAT = re.compile(r"eligibility check failed|connection reset|connection refused|"
                      r"failed to refresh|unauthenticated|network is unreachable|"
                      r"could not resolve|timeout waiting for.*auth|"
                      # 401/403 只認 HTTP 狀態碼的寫法；2026-09-22 裸數字比對會被分析內容裡的
                      # 股價、檔數之類數字誤觸，把家裡網路誤列黑名單，市場分析停了三天
                      r"\b(?:http|status|code|error)\W{0,3}(?:401|403)\b|\b(?:401|403) (?:unauthorized|forbidden)\b",
                      re.I)
# 伺服器端暫時性錯誤：不是網路被擋，不能列黑名單
TRANSIENT_PAT = re.compile(r"stream was interrupted|please continue the task|rate limit|"
                           r"resource exhausted|overloaded|internal error|503|502",
                           re.I)


def _sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=4).stdout.strip()
    except Exception:
        return ""


# 封鎖網域：比網段可靠。同一個場域的網段很多，換一個網段就會漏；
# 但 DHCP 發下來的 DNS 搜尋網域在場域內每個網段都一樣。
def _zones_config() -> dict:
    """讀本機地點設定；每次呼叫都重讀，改設定檔不必重啟常駐程式。"""
    try:
        return json.loads(ZONES_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"agy_guard：{ZONES_FILE} 讀取失敗（{type(e).__name__}），網域與區域規則暫不生效",
              file=sys.stderr)
        return {}


def blocked_domains() -> dict[str, str]:
    """{網域: 說明}：DNS 搜尋網域符合就一律不啟動 agy。"""
    return dict(_zones_config().get("blocked_domains") or {})


def known_zones() -> list[dict]:
    """選單列顯示用的已知區域。"""
    return list(_zones_config().get("zones") or [])


def search_domains() -> set[str]:
    """目前網路的 DNS 搜尋網域（小寫）。取不到就回空集合。"""
    return {d.lower() for d in re.findall(r"search domain\[\d+\]\s*:\s*(\S+)", _sh("scutil --dns"))}


def blocked_domain() -> tuple[str, str] | None:
    """目前網路屬於封鎖網域就回傳 (網域, 說明)。"""
    rules = blocked_domains()
    for d in search_domains():
        for bd, note in rules.items():
            if d == bd or d.endswith("." + bd):
                return bd, note
    return None


def fingerprint() -> dict:
    """目前網路的指紋。閘道 MAC 是主鍵；網段留著給人看。"""
    ip = ""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(0.5)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
    except Exception:
        pass
    gw = ""
    m = re.search(r"gateway:\s*([\d.]+)", _sh("route -n get default"))
    if m:
        gw = m.group(1)
    mac = ""
    if gw:
        a = _sh(f"arp -n {gw}")
        mm = re.search(r"at ([0-9a-f:]{11,17})", a, re.I)
        if mm:
            mac = mm.group(1).lower()
    subnet = ".".join(ip.split(".")[:3]) + "." if ip.count(".") == 3 else ""
    return {"gw_mac": mac, "gw": gw, "subnet": subnet, "ip": ip}


# 已知的網路區域（zones.json 的 zones），給選單列小工具與各排程共用同一個判斷。
# 判斷順序：DNS 網域 → 閘道 MAC → 閘道 IP → 網段。只用本機訊號、不連外，一秒內回傳。
# 網段很多的場域建議只用網域或閘道 MAC 判斷：像 192.168.1.x 這類網段到處都有，
# 拿來判斷會把別的網路誤認成同一個場域。


def _norm_mac(m: str) -> str:
    """macOS 的 arp 會省略前導零（0:da:…），統一補成兩位數。"""
    try:
        return ":".join(f"{int(x, 16):02x}" for x in m.split(":"))
    except ValueError:
        return m.lower()


def network_zone(fp: dict | None = None) -> dict:
    """目前所在的網路區域。

    回傳 id／name／short（區域）、why（靠哪個訊號判斷）、ip、gw、gw_mac、
    domains（DNS 搜尋網域，不含 Tailscale 的 ts.net）、bridge（雷電線是否接著）、
    blocked（在黑名單或封鎖網域上就是說明字串，否則 None）。
    """
    fp = fp or fingerprint()
    doms = search_domains()
    mac = _norm_mac(fp["gw_mac"]) if fp.get("gw_mac") else ""
    zone = {"id": "unknown", "name": "未知網路", "short": "?", "why": ""}
    if not fp.get("ip"):
        zone = {"id": "offline", "name": "未連網", "short": "離線", "why": "沒有 IP"}
    else:
        for z in known_zones():
            if any(d == zd or d.endswith("." + zd) for d in doms for zd in z.get("domains", [])):
                why = "DNS 網域"
            elif mac and mac in z.get("gw_macs", []):
                why = "閘道 MAC"
            elif fp.get("gw") in z.get("gateways", []):
                why = "閘道 IP"
            elif fp.get("subnet") and fp["subnet"] in z.get("subnets", []):
                why = "網段"
            else:
                continue
            zone = {"id": z["id"], "name": z["name"], "short": z["short"], "why": why}
            break
    return {**zone, "ip": fp.get("ip", ""), "gw": fp.get("gw", ""), "gw_mac": mac,
            "domains": sorted(d for d in doms if not d.endswith(".ts.net")),
            "bridge": bool(_sh("ipconfig getifaddr bridge0")),
            "blocked": blocked(fp)}


def _load():
    if BLOCK.exists():
        try:
            return json.loads(BLOCK.read_text())
        except Exception:
            pass
    return {"entries": []}


def _key(fp):
    return fp.get("gw_mac") or fp.get("subnet") or ""


def blocked(fp=None) -> str | None:
    """目前網路在黑名單上就回傳說明字串，否則 None。"""
    fp = fp or fingerprint()
    dom = blocked_domain()
    if dom:
        return (f"這個網路（{fp.get('ip')}，DNS 網域 {dom[0]}）屬於封鎖網域：{dom[1]}。\n"
                f"直接拒絕，不啟動 agy —— 失敗的 token 刷新會弄壞登入狀態。\n"
                f"網域規則寫在 {ZONES_FILE} 的 blocked_domains，unblock 解不掉；換網路後即可正常使用。")
    k = _key(fp)
    sub = fp.get("subnet")
    if not (k or sub):
        return None
    for e in _load()["entries"]:
        # 閘道 MAC 或網段任一命中就算 —— 手動預先加入的條目拿不到當時的 MAC，
        # 只有網段；而同一個 VLAN 換發不同 IP 時 MAC 仍然穩定。兩條都要比。
        if (k and e.get("key") == k) or (sub and e.get("subnet") == sub):
            n = e.get("failures", 1)
            # 自動記錄的條目要累積到 AUTO_BLOCK_AFTER 次才真的擋：
            # 2026-09-16 家裡與學校各因一次暫時性失敗（剛喚醒 DNS 未就緒）被永久列黑，
            # market-pulse 連續兩天沒分析。手動加的條目仍然一次就擋。
            if str(e.get("note", "")).startswith("自動記錄") and n < AUTO_BLOCK_AFTER:
                continue
            return (f"這個網路（{fp.get('ip')} / 閘道 {fp.get('gw')}）之前失敗過 {n} 次，"
                    f"已列入 agy 黑名單：{e.get('note','')}。\n"
                    f"直接拒絕，不啟動 agy —— 失敗的 token 刷新會弄壞登入狀態。\n"
                    f"換網路後即可正常使用；要解除請跑："
                    f"python3 /Users/Shared/antigravity-bridge/agy_guard.py unblock")
    return None


def record_failure(note="", fp=None):
    fp = fp or fingerprint()
    k = _key(fp)
    if not k:
        return False
    d = _load()
    for e in d["entries"]:
        if e.get("key") == k:
            # 2026-09-30：同一事件只算一次。agy_meter.quota() 失敗時內建隔 5 秒重試，
            # 一次暫時性失敗會連記兩筆，直接湊滿 AUTO_BLOCK_AFTER（9/23 熱點 08:57:22／:29 就是這樣被封）。
            try:
                since = time.time() - time.mktime(time.strptime(e.get("last", ""), "%Y-%m-%d %H:%M:%S"))
            except ValueError:
                since = INCIDENT_WINDOW
            if since >= INCIDENT_WINDOW:
                e["failures"] = e.get("failures", 1) + 1
            e["last"] = time.strftime("%F %T")
            break
    else:
        d["entries"].append({"key": k, "failures": 1, "note": note or "自動記錄",
                             "first": time.strftime("%F %T"),
                             "last": time.strftime("%F %T"), **fp})
    GUARD.mkdir(parents=True, exist_ok=True)
    BLOCK.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    return True


def unblock(key=None):
    d = _load()
    k = key or _key(fingerprint())
    before = len(d["entries"])
    d["entries"] = [e for e in d["entries"] if e.get("key") != k]
    BLOCK.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    return before - len(d["entries"])


def backup_token():
    if TOKEN.exists() and TOKEN.stat().st_size > 0:
        GUARD.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TOKEN, TOKBK)
        return True
    return False


def restore_token():
    if TOKBK.exists() and TOKBK.stat().st_size > 0:
        shutil.copy2(TOKBK, TOKEN)
        return True
    return False


def looks_like_network_failure(text: str) -> bool:
    if not text:
        return False
    if TRANSIENT_PAT.search(text) and not re.search(r"eligibility check failed|connection reset", text, re.I):
        return False
    return bool(FAIL_PAT.search(text))


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    fp = fingerprint()
    if cmd == "check":
        # 給 shim 用：被封鎖就把說明印到 stdout（非空＝擋下），否則什麼都不印
        b = blocked(fp)
        if b:
            print(b)
        sys.exit(0)
    if cmd == "onfail":
        # 給 shim 用：這次呼叫失敗了，判斷是不是網路/認證問題
        txt = ""
        if len(sys.argv) > 2:
            try:
                txt = open(sys.argv[2], errors="ignore").read()[-8000:]
            except Exception:
                pass
        # 2026-10-01：登入失效（Authentication required）和網路無關，換到哪個網路都一樣會失敗；
        # 以前把它當網路問題，導致家裡網路被誤列黑名單。改成不封鎖網路、通知使用者重新登入（每 6 小時最多一次）。
        if re.search(r"Authentication required|Please visit the URL to log in", txt, re.I):
            mark = GUARD / "auth_required.flag"
            import time
            if not mark.exists() or time.time() - mark.stat().st_mtime > 6 * 3600:
                mark.write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
                notifier = Path.home() / ".local/bin/report-notify"
                if notifier.exists():
                    subprocess.run([str(notifier), "--tag", "Antigravity", "--title", "Antigravity 登入失效",
                                    "--text", "agy 回報 Authentication required：登入已過期，和網路無關。請在 MBP 終端機執行 agy 依提示重新登入 Google 帳號；登入前所有派工會失敗。"],
                                   capture_output=True, timeout=60)
            print("⚠️ Antigravity 登入已失效（和網路無關，不封鎖這個網路）。請在終端機執行 agy 重新登入。")
            sys.exit(0)
        if looks_like_network_failure(txt):
            record_failure("自動記錄：呼叫失敗且訊息像網路/認證問題", fp)
            # 只有 token 檔不見或空掉才還原備份：2026-09-16 每次失敗都把 09-13 的舊備份蓋回去，
            # 反而讓有效的登入被覆蓋成過期 token，接著每個網路都被判成「連不上」
            restored = restore_token() if (not TOKEN.exists() or TOKEN.stat().st_size == 0) else False
            print(f"⚠️ 這個網路（{fp['ip']} / 閘道 {fp['gw']}）看起來連不上 Antigravity，"
                  f"已列入黑名單，之後不再嘗試。"
                  + ("已還原先前備份的 token。" if restored else ""))
        sys.exit(0)
    if cmd == "status":
        print(f"目前網路：IP {fp['ip']}　閘道 {fp['gw']}　閘道MAC {fp['gw_mac']}")
        print(f"DNS 網域：{' '.join(sorted(search_domains())) or '（無）'}"
              f"　封鎖網域：{', '.join(blocked_domains()) or '（未設定）'}")
        b = blocked(fp)
        print("狀態：" + ("🚫 已封鎖\n" + b if b else "✅ 可用"))
        d = _load()
        if d["entries"]:
            print(f"\n黑名單 {len(d['entries'])} 筆：")
            for e in d["entries"]:
                print(f"  {e.get('subnet','?')}x  閘道MAC {e.get('key')}  "
                      f"失敗 {e.get('failures')} 次  {e.get('note','')}")
        print(f"\ntoken 備份：{'有' if TOKBK.exists() else '無'}"
              f"{'（' + time.strftime('%F %T', time.localtime(TOKBK.stat().st_mtime)) + '）' if TOKBK.exists() else ''}")
    elif cmd == "zone":
        z = network_zone(fp)
        print(f"區域：{z['name']}（依 {z['why'] or '無法判斷'}）")
        print(f"IP {z['ip']}　閘道 {z['gw']}　閘道MAC {z['gw_mac'] or '（未取得）'}")
        print(f"DNS 網域：{' '.join(z['domains']) or '（無）'}　雷電線：{'已接' if z['bridge'] else '未接'}")
        print("Antigravity：" + ("🚫 停用\n" + z["blocked"] if z["blocked"] else "✅ 可用"))
    elif cmd == "block":
        note = sys.argv[2] if len(sys.argv) > 2 else "手動加入"
        record_failure(note, fp); print(f"已封鎖 {fp['subnet']}x（閘道MAC {fp['gw_mac']}）")
    elif cmd == "unblock":
        n = unblock(sys.argv[2] if len(sys.argv) > 2 else None)
        print(f"已解除 {n} 筆")
    elif cmd == "backup":
        print("已備份 token" if backup_token() else "token 不存在或是空的")
    elif cmd == "restore":
        print("已還原 token" if restore_token() else "沒有備份可還原")
    else:
        print(__doc__)
