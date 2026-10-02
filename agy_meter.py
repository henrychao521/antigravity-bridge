"""Antigravity (AGY) 用量與額度採集模組 (agy_meter.py)

此模組提供 Antigravity 側的 API 呼叫次數、Token 消耗量以及配額狀態採集功能，
僅使用 Python 3.12 標準函式庫，適用於多平台整合用量報表。
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import time


QUOTA_CACHE_PATH = Path(__file__).resolve().parent / "quota_cache.json"
QUOTA_LAST: dict = {"error": None, "from_cache": False, "fetched_at": None}


def _parse_usage(stdout: str) -> list[dict]:
    start_idx, end_idx = stdout.find("{"), stdout.rfind("}")
    if start_idx == -1 or end_idx == -1 or start_idx > end_idx:
        return []
    data = json.loads(stdout[start_idx: end_idx + 1])
    groups = data.get("command", {}).get("data", {}).get("groups", [])
    if not isinstance(groups, list):
        return []
    results: list[dict] = []
    for g in groups:
        group_name = g.get("group") or g.get("name") or "unknown"
        buckets = g.get("buckets") or g.get("limits") or [g]
        if not isinstance(buckets, list):
            buckets = [buckets]
        for b in buckets:
            try:
                rem_frac = float(b.get("remaining_fraction", 0.0))
            except (ValueError, TypeError):
                rem_frac = 0.0
            reset_raw = b.get("reset_time")
            reset_dt: datetime | None = None
            if isinstance(reset_raw, str) and reset_raw:
                try:
                    reset_dt = datetime.fromisoformat(reset_raw.strip().replace("Z", "+00:00"))
                except ValueError:
                    reset_dt = None
            elif isinstance(reset_raw, (int, float)):
                reset_dt = datetime.fromtimestamp(reset_raw, tz=timezone.utc)
            results.append({"group": g.get("group", group_name), "bucket_id": b.get("bucket_id", b.get("id", "")),
                            "window": b.get("window", ""), "remaining_fraction": rem_frac,
                            "reset_time": reset_dt, "used_pct": round((1.0 - rem_frac) * 100, 2)})
    return results


def _classify_failure(returncode, stdout: str, stderr: str) -> str:
    text = f"{stdout}\n{stderr}".lower()
    if any(k in text for k in ("not logged in", "not signed in", "please log in", "please sign in", "unauthenticated",
                               "login required", "invalid_grant", "reauth")):
        return "未登入"
    if "eligibility check failed" in text or "connection reset" in text or "network" in text:
        return "網路或服務暫時錯誤"
    return f"查詢失敗（exit {returncode}）" if returncode not in (0, None) else "回應無法解析"


def quota() -> list[dict]:
    """取得 Antigravity 當前配額狀態。

    透過 `agy -p "/usage" --output-format json` 取得。2026-09-10 修正：
    以前任何失敗都回空串列，小工具就一律顯示「agy 未登入？」——實際上多半是逾時或暫時錯誤。
    現在失敗會重試一次，並把原因寫進 QUOTA_LAST["error"]（未安裝／逾時／未登入／網路／查詢失敗）；
    兩次都失敗時回傳上一次成功的快取（QUOTA_LAST["from_cache"]=True、fetched_at＝當時時間）。
    """
    agy_bin = Path.home() / ".local" / "bin" / "agy"
    QUOTA_LAST.update({"error": None, "from_cache": False})
    if not agy_bin.exists():
        QUOTA_LAST["error"] = "agy 未安裝"
        return []
    err = None
    for attempt in range(2):
        try:
            proc = subprocess.run([str(agy_bin), "-p", "/usage", "--output-format", "json"],
                                  capture_output=True, text=True, timeout=90)
            results = _parse_usage(proc.stdout) if proc.returncode == 0 else []
            if results:
                now = datetime.now().astimezone()
                QUOTA_LAST.update({"error": None, "fetched_at": now})
                try:
                    QUOTA_CACHE_PATH.write_text(json.dumps({"fetched_at": now.isoformat(), "buckets": [
                        {**r, "reset_time": r["reset_time"].isoformat() if r["reset_time"] else None} for r in results]},
                        ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass
                return results
            err = _classify_failure(proc.returncode, proc.stdout, proc.stderr)
        except subprocess.TimeoutExpired:
            err = "查詢逾時（90 秒）"
        except Exception as e:
            err = f"查詢失敗（{type(e).__name__}）"
        if attempt == 0:
            time.sleep(5)
    QUOTA_LAST["error"] = err
    try:
        cache = json.loads(QUOTA_CACHE_PATH.read_text(encoding="utf-8"))
        QUOTA_LAST.update({"from_cache": True, "fetched_at": datetime.fromisoformat(cache["fetched_at"])})
        return [{**b, "reset_time": datetime.fromisoformat(b["reset_time"]) if b.get("reset_time") else None}
                for b in cache.get("buckets", [])]
    except Exception:
        return []


def calls(since: datetime | None = None) -> list[dict]:
    """掃描 Antigravity CLI 日誌並擷取所有 API 呼叫記錄。

    掃描 `~/.gemini/antigravity-cli/log/cli-*.log`，以檔名時間作為近似時間戳。

    【實測警告 2026-08-29】此來源結構性不完整：只有 Anthropic 路徑
    (API_PROVIDER_ANTHROPIC_VERTEX) 會在日誌寫出 usage:{} 行，Gemini 呼叫
    完全不寫。因此本函式只能當「互動式 TUI 用量」的粗略補漏，
    正式統計請改用 ledger()（由 run() 記錄，涵蓋所有模型）。

    Args:
        since (datetime | None): 起始時間過濾點（包含時區或預設為本地時區）。

    Returns:
        list[dict]: 呼叫記錄清單，每筆包含 ts, ts_is_file_level, input_tokens,
                    output_tokens, api_provider, quota_group。
    """
    log_dir = Path.home() / ".gemini" / "antigravity-cli" / "log"
    if not log_dir.exists() or not log_dir.is_dir():
        return []

    # 確保 since 為帶時區物件以便比對
    if since is not None and since.tzinfo is None:
        since = since.astimezone()

    results: list[dict] = []
    log_files = sorted(log_dir.glob("cli-*.log"))

    filename_pattern = re.compile(r"^cli-(\d{8})_(\d{6})\.log$")

    for file_path in log_files:
        match = filename_pattern.match(file_path.name)
        if not match:
            continue

        dt_str = f"{match.group(1)}_{match.group(2)}"
        try:
            file_dt = datetime.strptime(dt_str, "%Y%m%d_%H%M%S").astimezone()
        except ValueError:
            continue

        if since is not None and file_dt < since:
            continue

        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "usage:{" not in line:
                        continue

                    in_match = re.search(r"input_tokens:(\d+)", line)
                    out_match = re.search(r"output_tokens:(\d+)", line)
                    prov_match = re.search(r"api_provider:([^\s,}]+)", line)

                    if not (in_match and out_match):
                        continue

                    in_tokens = int(in_match.group(1))
                    out_tokens = int(out_match.group(1))
                    api_provider = prov_match.group(1) if prov_match else ""

                    # 判斷配額群組 (ANTHROPIC 優先判定)
                    prov_upper = api_provider.upper()
                    if any(
                        k in prov_upper for k in ("ANTHROPIC", "OPENAI", "GPT")
                    ):
                        quota_group = "Claude and GPT models"
                    elif any(
                        k in prov_upper for k in ("GOOGLE", "GEMINI", "VERTEX")
                    ):
                        quota_group = "Gemini Models"
                    else:
                        quota_group = "unknown"

                    results.append(
                        {
                            "ts": file_dt,
                            "ts_is_file_level": True,
                            "input_tokens": in_tokens,
                            "output_tokens": out_tokens,
                            "api_provider": api_provider,
                            "quota_group": quota_group,
                        }
                    )
        except Exception:
            continue

    return results


BASE = Path(__file__).resolve().parent
LEDGER = BASE / "ledger.jsonl"
QUOTA_CSV = BASE / "quota_history.csv"
_CSV_COLS = ["ts", "gemini_5h", "gemini_weekly", "tp_5h", "tp_weekly",
             "gemini_5h_reset", "tp_5h_reset"]


def log_quota_sample(buckets: list[dict] | None = None) -> bool:
    """把一次額度快照追加進 quota_history.csv。

    為什麼只取樣額度、不取樣 Claude 用量：Claude 的每次呼叫都已經完整寫在
    ~/.claude/projects 的 transcripts 裡（含時間戳），任何時候都能回溯重算；
    但 Antigravity 的「剩餘百分比」是查了才知道、過了就查不到的瞬時值，
    不定時取樣就永遠補不回來。
    """
    import csv

    buckets = buckets if buckets is not None else quota()
    if not buckets:
        return False
    by_id = {b["bucket_id"]: b for b in buckets}

    def pct(bid: str):
        b = by_id.get(bid)
        return round(b["remaining_fraction"] * 100, 3) if b else ""

    def reset(bid: str):
        b = by_id.get(bid)
        return b["reset_time"].isoformat() if b and b.get("reset_time") else ""

    row = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gemini_5h": pct("gemini-5h"), "gemini_weekly": pct("gemini-weekly"),
        "tp_5h": pct("3p-5h"), "tp_weekly": pct("3p-weekly"),
        "gemini_5h_reset": reset("gemini-5h"), "tp_5h_reset": reset("3p-5h"),
    }
    new = not QUOTA_CSV.exists()
    try:
        with QUOTA_CSV.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=_CSV_COLS)
            if new:
                w.writeheader()
            w.writerow(row)
        return True
    except OSError:
        return False


def run(prompt: str, model: str | None = None, schema: str | None = None,
        timeout: int = 600, measure_quota: bool = True,
        conversation: str | None = None, note: str = "",
        print_timeout: str | None = None) -> dict:
    """呼叫 agy 並把用量記進 ledger.jsonl。所有派工都應該走這裡。

    measure_quota=True 時，呼叫前後各拍一次額度快照（查詢本身 0 token），
    據此算出「這一次呼叫吃掉幾 % 配額」——這是推估剩餘可用次數的唯一可靠依據。
    """
    blocked = network_note()
    if blocked:
        return {"status": "NETWORK_BLOCKED", "error": blocked, "response": ""}
    agy_bin = Path.home() / ".local" / "bin" / "agy"
    before = _quota_map() if measure_quota else {}
    started = datetime.now().astimezone()

    cmd = [str(agy_bin), "-p", prompt, "--output-format", "json"]
    # ⚠️ agy 的 --print-timeout 預設只有 5 分鐘,超過會回 status: ERROR、
    #    **回應是空的但工作已經做掉了**(規範第五節第 4 條;實測燒掉 140k tokens 拿不到輸出)。
    #    這裡預設與本地 timeout 對齊,長任務(尤其會呼叫 MCP 工具的)不再白燒。
    cmd += ["--print-timeout", print_timeout or f"{max(1, int(timeout // 60))}m"]
    if model:
        cmd += ["--model", model]
    if schema:
        cmd += ["--json-schema", schema]
    if conversation:
        cmd += ["--conversation", conversation]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        raw = proc.stdout
        data = json.loads(raw[raw.index("{"):]) if "{" in raw else {}
    except Exception as e:
        data = {"status": "LOCAL_ERROR", "error": str(e)}

    after = _quota_map() if measure_quota else {}
    # 額度差值：before - after，正數代表被吃掉的比例（換算成百分點）
    delta = {k: round((before[k] - after[k]) * 100, 4)
             for k in before if k in after}

    entry = {
        "ts": started.isoformat(),
        "model": model or "(default)",
        "status": data.get("status"),
        "conversation_id": data.get("conversation_id"),
        "duration_seconds": data.get("duration_seconds"),
        "usage": data.get("usage", {}),
        "quota_delta_pct": delta,
        "prompt_chars": len(prompt),
        "note": note,
        "response": (data.get("response") or ""),
    }
    slim = {k: v for k, v in entry.items() if k != "response"}
    slim["resp_chars"] = len(entry["response"])
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(slim, ensure_ascii=False) + "\n")
    data["response"] = entry["response"]
    return data


def supervise(task: str, criteria: str, check, model: str = "gemini-3.1-pro-high",
              max_rounds: int = 3, timeout: int = 1800, journal=None) -> dict:
    """主管模式：派工 → 驗收 → 退回重做，直到通過或用完回合。

    check(output_text) 必須回傳 (ok: bool, feedback: str)。
    feedback 會原封不動退回給它，並且用 --conversation 續談，
    所以它看得到自己上一版寫了什麼，不是從零重寫。

    為什麼要有這個：模型「自認完成」與「真的通過」是兩回事。驗收條件必須是
    機器可判定的（跑得起來、數字對得上、schema 合格），不能是「看起來不錯」。
    """
    conv = None
    rounds = []
    for r in range(1, max_rounds + 1):
        prompt = task if r == 1 else (
            f"上一版沒有通過驗收。驗收者的意見如下，請據此修正後重新提交完整版本：\n\n{fb}")
        cmd_extra = {"conversation": conv} if conv else {}
        data = run(prompt + ("\n\n【驗收條件】\n" + criteria if r == 1 else ""),
                   model=model, timeout=timeout, measure_quota=False,
                   note=f"supervise r{r}", **cmd_extra)
        conv = data.get("conversation_id") or conv
        text = data.get("response", "")
        ok, fb = check(text)
        rounds.append({"round": r, "ok": ok, "feedback": fb[:400],
                       "chars": len(text), "status": data.get("status")})
        print(f"  第 {r} 回合：{'✅ 通過' if ok else '❌ 退回'} — {fb[:70]}")
        if ok:
            return {"ok": True, "rounds": rounds, "output": text, "conversation_id": conv}
    return {"ok": False, "rounds": rounds, "output": text, "conversation_id": conv}


def _quota_map() -> dict[str, float]:
    """把 quota() 攤成 {bucket_id: remaining_fraction}，方便相減。"""
    return {q["bucket_id"]: q["remaining_fraction"] for q in quota()}


def ledger() -> list[dict]:
    """讀出 run() 累積的完整用量帳本（涵蓋所有模型，與日誌不同）。"""
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def summary(since: datetime | None = None) -> dict:
    """彙整指定時間以來的用量與目前額度。

    Args:
        since (datetime | None): 起始時間過濾點。

    Returns:
        dict: 包含 by_group 群組統計、total_calls 總呼叫數與 quota 額度資訊。
    """
    call_list = calls(since)
    by_group: dict[str, dict[str, int]] = {}

    for c in call_list:
        grp = c["quota_group"]
        if grp not in by_group:
            by_group[grp] = {"calls": 0, "input_tokens": 0, "output_tokens": 0}
        by_group[grp]["calls"] += 1
        by_group[grp]["input_tokens"] += c["input_tokens"]
        by_group[grp]["output_tokens"] += c["output_tokens"]

    return {
        "by_group": by_group,
        "total_calls": len(call_list),
        "quota": quota(),
    }


if __name__ == "__main__":
    report = summary()
    print("=" * 65)
    print("【Antigravity 用量與額度摘要報告】")
    print("=" * 65)
    print(f"總呼叫次數: {report['total_calls']}")

    print("\n[依模型群組統計]")
    if not report["by_group"]:
        print("  尚無符合條件的呼叫紀錄")
    else:
        for grp_name, stats in report["by_group"].items():
            print(f"  ● 群組: {grp_name}")
            print(f"    - 呼叫次數: {stats['calls']}")
            print(f"    - 輸入 Token: {stats['input_tokens']:,}")
            print(f"    - 輸出 Token: {stats['output_tokens']:,}")

    print("\n[當前配額狀態 (Quota)]")
    if not report["quota"]:
        print("  無法取得額度資訊 (agy 指令未安裝或執行失敗)")
    else:
        for q in report["quota"]:
            reset_text = (
                q["reset_time"].strftime("%Y-%m-%d %H:%M:%S %Z")
                if q["reset_time"]
                else "N/A"
            )
            print(
                f"  ● {q['group']} | 窗口: {q['window']} | 貯體: {q['bucket_id']}"
            )
            print(
                f"    - 使用率: {q['used_pct']}% (剩餘比率: {q['remaining_fraction'] * 100:.1f}%)"
            )
            print(f"    - 重設時間: {reset_text}")
    print("=" * 65)


# ── 工具模式（2026-08-31 實測後新增）────────────────────────────────────────
# headless 下 Antigravity **是有工具的**（view_file / run_command / write_to_file /
# read_url_content / search_web / grep_search / browser_*）。
# 之前以為「純文字進出」，其實是因為：
#   1. 工具呼叫要通過 ~/.gemini/antigravity-cli/settings.json 的 permissions.allow，
#      比對的是**指令名稱**，完整路徑不匹配 command(python) 這種寫法；
#   2. 碰到工作區外的路徑要看 trustedWorkspaces；
#   3. **工具呼叫一旦被拒，該回合直接結束、response 是空字串**——
#      看起來像「沒有工具」，其實是權限沒開。
# 用 --output-format stream-json 才看得到工具呼叫與其輸出。

# 已知會封鎖 Antigravity 的網路。實測在某些學校網路下，
# agy 對 daily-cloudcode-pa.googleapis.com 的 eligibility check 會被中斷
# （connection reset by peer），而且失敗的 token 刷新會讓登入狀態失效。
# 在這種網路下重試沒有意義，只會浪費時間並可能弄壞登入。
# 清單放在本機的 blocked_subnets.local.json（不上傳），格式：{"10.20.30.": "說明"}
def _load_blocked_subnets() -> dict:
    try:
        return json.loads((Path(__file__).with_name("blocked_subnets.local.json")).read_text(encoding="utf-8"))
    except Exception:
        return {}


BLOCKED_SUBNETS = _load_blocked_subnets()


def network_note() -> str | None:
    """若目前在已知會封鎖的網路，回傳說明字串；否則 None。

    兩層：agy_guard 的**自學黑名單**（閘道 MAC 指紋，會隨失敗自己長大）優先，
    再退回 BLOCKED_SUBNETS 這份寫死的清單。
    改成自學是因為實測同一所學校至少有兩個網段（一個失敗、一個正常），
    寫死一定會漏，而漏掉的代價是又一次壞掉的登入。
    """
    try:
        import agy_guard
        b = agy_guard.blocked()
        if b:
            return b
    except Exception:
        pass
    try:
        import socket
        s_ = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s_.settimeout(0.5)
        s_.connect(("8.8.8.8", 80))
        ip = s_.getsockname()[0]
        s_.close()
    except Exception:
        return None
    for prefix, why in BLOCKED_SUBNETS.items():
        if ip.startswith(prefix):
            return f"目前位於 {ip}——{why}。派工會失敗，先換網路再試，不要反覆重試。"
    return None


def run_with_tools(prompt: str, model: str | None = None, timeout: int = 900,
                   note: str = "", print_timeout: str | None = None) -> dict:
    """允許 Antigravity 使用工具的派工，回傳含工具呼叫軌跡。

    **不要用在會吃進不可信內容的任務上**（例如把新聞餵進去分析）：
    允許清單裡有 write_file(*)，新聞標題裡的注入指令可能觸發寫檔。
    只用在提示內容完全由自己掌控的任務：查證、跑測試、產生程式碼後自我驗證。
    """
    blocked = network_note()
    if blocked:
        return {"status": "NETWORK_BLOCKED", "error": blocked, "response": "", "steps": [], "denied": []}
    agy_bin = Path.home() / ".local" / "bin" / "agy"
    cmd = [str(agy_bin), "-p", prompt, "--output-format", "stream-json"]
    # 與 run() 一致：放寬 agy 自己的 --print-timeout（預設 5 分鐘，超過回空但工作已做掉）。
    # 2026-09-10 補上：批次 generate_image 一輪常超過 5 分鐘。
    cmd += ["--print-timeout", print_timeout or f"{max(1, int(timeout // 60))}m"]
    if model:
        cmd += ["--model", model]
    started = datetime.now().astimezone()
    steps, result = [], {}
    # Google 端的 eligibility check 偶爾會 connection reset（實測 2026-08-31），
    # 那是基礎設施的暫時性錯誤，值得重試一次再放棄。
    attempts = 0
    try:
        while True:
            attempts += 1
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            out_ = proc.stdout or ""
            # 網路被擋時重試無用，而且失敗的 token 刷新可能弄壞登入狀態
            if "Eligibility check failed" in out_ and network_note():
                break
            if "Eligibility check failed" not in out_ or attempts >= 3:
                break
            time.sleep(4 * attempts)
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            su = e.get("step_update") or {}
            if su.get("step_type") == "tool":
                ti = su.get("tool_info") or {}
                steps.append({"tool": su.get("tool_name"), "state": su.get("state"),
                              "params": ti.get("parameters"),
                              "output": (ti.get("output") or "")[:4000],
                              "error": (ti.get("error") or {}).get("message")})
            if e.get("event") == "result":
                result = e.get("result") or {}
    except Exception as e:
        result = {"status": "LOCAL_ERROR", "error": str(e)}

    denied = [s for s in steps if s.get("error") and "permission" in str(s["error"]).lower()]
    signals = _record_tool_signals(steps)
    entry = {"ts": started.isoformat(), "model": model or "(default)",
             "status": result.get("status"), "conversation_id": result.get("conversation_id"),
             "duration_seconds": result.get("duration_seconds"),
             "usage": result.get("usage", {}), "quota_delta_pct": {},
             "prompt_chars": len(prompt), "note": note or "run_with_tools",
             "tool_calls": len(steps), "tool_denied": len(denied),
             "tools_used": signals["tools_used"], "image_ok": signals["image_ok"],
             "image_err": signals["image_err"],
             "response": result.get("response") or ""}
    slim = {k: v for k, v in entry.items() if k != "response"}
    slim["resp_chars"] = len(entry["response"])
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(slim, ensure_ascii=False) + "\n")
    return {**result, "response": entry["response"], "steps": steps,
            "denied": [d["params"] for d in denied]}


# ═══════════════ 2026-09-10 擴充：生圖數量、G1 credits、能力盤點 ═══════════════
# /usage 只回報「Gemini」「Claude/GPT」兩組文字模型配額；生圖（gemini-3.1-flash-image）
# 有獨立的小配額，但 CLI 完全不揭露——只有用完時 429 錯誤的 metadata 會寫出重置時間。
# 所以這裡用三個來源拼出生圖狀態：
#   ① brain 目錄裡實際產出的圖檔（真實張數，含互動模式）
#   ② run_with_tools() 捕捉到的 429 事件（重置時間）
#   ③ 由 ①② 回推的「每個窗口大約可生幾張」
BRAIN = Path.home() / ".gemini" / "antigravity-cli" / "brain"
IMAGE_STATE = BASE / "image_quota.json"
CAPS_CACHE = BASE / "capabilities.json"
EXTRA_CSV = BASE / "extra_history.csv"
IMAGE_WINDOW_H = 5
_IMG_RE = re.compile(r"_\d{13}\.(?:jpe?g|png|webp)$", re.I)
_RESET_RE = re.compile(r'"quotaResetTimeStamp"\s*:\s*"([^"]+)"')
_MODEL_RE = re.compile(r'"model"\s*:\s*"([^"]+)"')


def _iso(v):
    if isinstance(v, datetime):
        return v if v.tzinfo else v.astimezone()
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def _slash(cmd: str, timeout: int = 60) -> dict:
    """執行 agy 的 slash 指令（/usage、/credits、/skills、/agents），不耗 token。"""
    agy_bin = Path.home() / ".local" / "bin" / "agy"
    try:
        out = subprocess.run([str(agy_bin), "-p", cmd, "--output-format", "json"],
                             capture_output=True, text=True, timeout=timeout).stdout
        return json.loads(out[out.index("{"): out.rindex("}") + 1])
    except Exception:
        return {}


def credits() -> dict | None:
    """G1 credits（配額用完後的加購點數）。回傳 {'remaining_credits': int, 'upgrade_uri': str}。"""
    for attempt in range(2):                      # 偶發取不到（2026-09-10 報表一次落空、隨後 5/5 成功），重試一次
        d = (_slash("/credits").get("command") or {}).get("data")
        if isinstance(d, dict) and "remaining_credits" in d:
            return d
        time.sleep(2)
    return None


def _image_files() -> list[tuple[float, Path]]:
    if not BRAIN.exists():
        return []
    out = []
    for f in BRAIN.glob("*/*"):
        if f.is_file() and _IMG_RE.search(f.name):
            try:
                out.append((f.stat().st_mtime, f))
            except OSError:
                pass
    return sorted(out)


def images(now: datetime | None = None) -> dict:
    """Antigravity 實際生成的圖片張數（依 brain 目錄檔案時間）。"""
    now = now or datetime.now().astimezone()
    t = now.timestamp()
    files = _image_files()
    def n(hours):
        return sum(1 for m, _ in files if t - m <= hours * 3600)
    return {"total": len(files), "last_5h": n(5), "last_24h": n(24), "last_7d": n(24 * 7),
            "last_image_at": datetime.fromtimestamp(files[-1][0]).astimezone() if files else None,
            "conversations": len({f.parent.name for _, f in files})}


def _load_image_state() -> dict:
    try:
        return json.loads(IMAGE_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"events": []}


def record_image_exhausted(detected_at, reset_time, model: str = "", source: str = "") -> dict | None:
    """記一筆「生圖配額用完」事件，並回推這個窗口實際生了幾張（＝推估上限）。"""
    det, rst = _iso(detected_at), _iso(reset_time)
    if not det or not rst:
        return None
    st = _load_image_state()
    if any(e.get("reset_time") == rst.isoformat() for e in st["events"]):
        return None                                    # 同一個窗口只記一次
    win_start = (rst - timedelta(hours=IMAGE_WINDOW_H)).timestamp()
    used = sum(1 for m, _ in _image_files() if win_start <= m <= det.timestamp() + 60)
    ev = {"detected_at": det.isoformat(), "reset_time": rst.isoformat(), "model": model,
          "images_in_window": used, "source": source}
    st["events"].append(ev)
    try:
        IMAGE_STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    return ev


def image_quota(now: datetime | None = None) -> dict:
    """生圖配額狀態（推估）。exhausted＝目前仍在 429 的窗口內。"""
    now = now or datetime.now().astimezone()
    st = _load_image_state()
    evs = st.get("events", [])
    ests = sorted(e["images_in_window"] for e in evs if e.get("images_in_window"))
    est_limit = ests[len(ests) // 2] if ests else None      # 取中位數
    last = evs[-1] if evs else None
    reset = _iso(last["reset_time"]) if last else None
    exhausted = bool(reset and now < reset)
    files = _image_files()
    if exhausted:
        start = reset - timedelta(hours=IMAGE_WINDOW_H)
    else:
        # 窗口從「上次重置後的第一張圖」起算 5 小時
        after = [m for m, _ in files if (not reset or m >= reset.timestamp()) and now.timestamp() - m <= IMAGE_WINDOW_H * 3600]
        start = datetime.fromtimestamp(after[0]).astimezone() if after else None
    used = sum(1 for m, _ in files if start and m >= start.timestamp()) if start else 0
    window_reset = reset if exhausted else (start + timedelta(hours=IMAGE_WINDOW_H) if start else None)
    return {"model": (last or {}).get("model") or "gemini-3.1-flash-image", "exhausted": exhausted,
            "used_in_window": used, "estimated_limit": est_limit,
            "estimated_remaining": (max(est_limit - used, 0) if est_limit is not None and not exhausted else (0 if exhausted else None)),
            "window_reset": window_reset, "samples": len(ests), "last_event": last}


def _record_tool_signals(steps: list[dict]) -> dict:
    """從一次 run_with_tools 的軌跡統計工具使用，並自動記下生圖 429。"""
    used: dict[str, int] = {}
    ok = err = 0
    for st in steps or []:
        if st.get("state") not in ("DONE", "ERROR"):
            continue
        tool = st.get("tool") or "?"
        used[tool] = used.get(tool, 0) + 1
        if tool == "generate_image":
            if st["state"] == "DONE":
                ok += 1
            else:
                err += 1
                msg = str(st.get("error") or "")
                if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                    r, mm = _RESET_RE.search(msg), _MODEL_RE.search(msg)
                    if r:
                        record_image_exhausted(datetime.now().astimezone(), r.group(1),
                                               mm.group(1) if mm else "", "run_with_tools")
    return {"tools_used": used, "image_ok": ok, "image_err": err}


def tool_usage(since: datetime | None = None) -> dict[str, int]:
    """帳本裡各工具的使用次數（只涵蓋 run_with_tools 派工，2026-09-10 之後才有逐工具紀錄）。"""
    out: dict[str, int] = {}
    for e in ledger():
        if since and _iso(e.get("ts")) and _iso(e["ts"]) < since:
            continue
        for k, v in (e.get("tools_used") or {}).items():
            out[k] = out.get(k, 0) + v
    return out


def capabilities(max_age_hours: int = 24, refresh_tools: bool = False) -> dict:
    """能力盤點（快取一天）：版本、模型、MCP、skills、agents、外掛、遠端控制。
    refresh_tools=True 時另外發一次最便宜的呼叫，從 init 事件讀完整工具清單（會耗少量 Gemini 配額）。"""
    try:
        cache = json.loads(CAPS_CACHE.read_text(encoding="utf-8"))
        age = datetime.now().astimezone() - _iso(cache["checked_at"])
        if age < timedelta(hours=max_age_hours) and not refresh_tools:
            return cache
    except Exception:
        cache = {}
    agy_bin = str(Path.home() / ".local" / "bin" / "agy")
    def run(args, t=60):
        try:
            return subprocess.run([agy_bin, *args], capture_output=True, text=True, timeout=t).stdout
        except Exception:
            return ""
    models = [ln.split("\t", 1) for ln in run(["models"]).splitlines() if "\t" in ln]
    mcp = [ln.split()[0] + ("" if "enabled" in ln else "（停用）") for ln in run(["mcp", "list"]).splitlines()[1:] if ln.strip()]
    skills = [x["name"] for x in ((_slash("/skills").get("command") or {}).get("data") or {}).get("skills", [])]
    agents = ((_slash("/agents").get("command") or {}).get("data") or {}).get("agents", [])
    caps = {"checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "version": run(["--version"]).strip(),
            "models": [{"id": a, "name": b} for a, b in models],
            "mcp_servers": mcp, "skills": skills, "agents": agents,
            "plugins": run(["plugin", "list"]).strip(),
            "remote_control": (run(["remote-control", "status"]).splitlines() or [""])[0],
            "tools": cache.get("tools", []), "tools_checked_at": cache.get("tools_checked_at")}
    if refresh_tools:
        try:
            out = subprocess.run([agy_bin, "--model", "gemini-3.7-flash-low", "--output-format", "stream-json",
                                  "-p=只回覆 OK"], capture_output=True, text=True, timeout=120).stdout
            for line in out.splitlines():
                m = re.search(r'"tools"\s*:\s*(\[[^\]]*\])', line)
                if m:
                    caps["tools"] = json.loads(m.group(1)); caps["tools_checked_at"] = caps["checked_at"]; break
        except Exception:
            pass
    prev = {m["id"] for m in cache.get("models", [])}
    caps["new_models"] = sorted({m["id"] for m in caps["models"]} - prev) if prev else []
    try:
        CAPS_CACHE.write_text(json.dumps(caps, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    return caps


def log_extra_sample(img: dict | None = None, cred: dict | None = None) -> bool:
    """生圖與 credits 的時序樣本（和 quota_history.csv 分開，不動舊欄位）。"""
    import csv
    img = img or image_quota()
    row = {"ts": datetime.now().astimezone().isoformat(timespec="seconds"),
           "images_5h": images()["last_5h"], "image_used_in_window": img["used_in_window"],
           "image_exhausted": int(img["exhausted"]),
           "image_window_reset": img["window_reset"].isoformat() if img.get("window_reset") else "",
           "g1_credits": (cred or {}).get("remaining_credits", "")}
    new = not EXTRA_CSV.exists()
    try:
        with EXTRA_CSV.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(row))
            if new:
                w.writeheader()
            w.writerow(row)
        return True
    except OSError:
        return False
