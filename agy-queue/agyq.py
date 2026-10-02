#!/usr/bin/env python3
"""agyq — Studio 放工作、MBP 用 Antigravity 執行的工作佇列（2026-09-25）。

為什麼有這個：Studio 放在學校，學校網路擋 Antigravity（agy_guard 以 DNS 網域辨識）；
MBP 在家時可以用。Studio 連不進 MBP（MBP 沒開 SSH），所以一律由 MBP 主動去 Studio 領工作。

佇列放在 Studio 的 ~/agy-queue/：
    inbox/          待處理（submit 放進來）
    claimed/        MBP 已領走、執行中
    done/           完成，結果已送回
    failed/         每個模型都沒產出合格結果
    waiting-cable/  結果大於 50 MB，等下次接雷電線由 linksync 送回

用法：
    agyq submit --title 標題 --task 任務說明.md --base 專案根目錄 檔案... [--models m1,m2]
    agyq submit-image --title 標題 --jobs images.json [--base 參考圖根目錄] [--urgent]
                        # 生圖需求（2026-10-02）：MBP 在家時用 Antigravity generate_image 生成，
                        # 額度不足時依 image_router 規則改走本機／程式繪製；只產靜態圖，Antigravity 不能生成影片
    agyq run            # MBP 的 launchd 每 10 分鐘呼叫一次
    agyq status
    agyq deliver-large  # linksync 在接上雷電線時呼叫

⚠️ 只能放可信任的工作。允許清單有 write_file(*)，不可把新聞、網頁、上傳檔這類
   不可信內容放進 task 或 materials（CLAUDE.md「不要派給它」）。
⚠️ 在封鎖網路（學校網域）時 run 什麼都不做：不領工作、不查額度、不碰 agy。
   執行途中只要遇到連線或認證類的失敗就整批延後並停止本輪，絕不重試，
   避免失敗的 token 刷新把登入弄壞（使用者 2026-09-24／25 的要求）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BRIDGE = Path("/Users/Shared/antigravity-bridge")
REMOTE = os.environ.get("AGYQ_REMOTE", "studio")        # "local" 表示佇列就在本機（Studio 上用）
QROOT = os.environ.get("AGYQ_ROOT", "agy-queue")        # 相對於佇列所在機器的家目錄
LOCAL_ROOT = Path(os.environ.get("AGYQ_LOCAL_ROOT", Path.home() / ".local/share/agyq"))   # 環境變數只給測試用
WORK = LOCAL_ROOT / "work"
OUTBOX_LARGE = LOCAL_ROOT / "outbox-large"
LOG = Path.home() / "Library/Logs/agyq.log"
LOCK = Path(os.environ.get("AGYQ_LOCK", "/tmp/agyq-runner.lock"))
SMALL_MAX = int(os.environ.get("AGYQ_SMALL_MAX", 50 * 1024 * 1024))   # 環境變數只給測試用
MIN_QUOTA = 0.10
# 週額度保留：大批審查不能把整週的額度吃光，其他派工還要用（2026-09-26 22 工具批次時加）
WEEKLY_RESERVE = {"Claude and GPT models": 0.30, "Gemini Models": 0.20}
STATES = ("inbox", "claimed", "done", "failed", "waiting-cable")
# 2026-09-25 使用者：多一些模型交叉查證比較好。四個家族、五種觀點
DEFAULT_MODELS = ["gemini-3.1-pro-high", "gemini-3.8-flash-high", "claude-sonnet-4-6",
                  "claude-opus-4-6-thinking", "gpt-oss-120b-medium"]
# 單次提示的字元上限。超過就把素材切成幾份分別審查再合併。
# gpt-oss-120b 實測：69k 字元可以、134k 字元回空白（上下文放不下）
MODEL_MAX_CHARS = {"gpt-oss-120b-medium": 60_000}
AREAS = {"內容正確性", "教學設計", "程式邏輯", "可用性", "無障礙", "效能", "架構", "安全", "維護性", "一致性", "用語"}
SEVERITIES = {"高", "中", "低"}


# ───────────────────────── 共用 ─────────────────────────
def log(msg: str) -> None:
    line = f"{dt.datetime.now():%F %T} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def q(state: str, jid: str = "") -> str:
    """佇列路徑（在佇列所在機器上的寫法）。"""
    return f"{QROOT}/{state}" + (f"/{jid}" if jid else "")


def rsh(cmd: str, check: bool = True, timeout: int = 120) -> subprocess.CompletedProcess:
    """在佇列所在機器上執行指令。"""
    if REMOTE == "local":
        full = ["/bin/bash", "-c", f"cd ~ && {cmd}"]
    else:
        full = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=30", REMOTE, cmd]
    p = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError(f"遠端指令失敗（{p.returncode}）：{cmd}\n{p.stderr.strip()[:300]}")
    return p


def rsync_to(local: Path, remote_path: str, via: str | None = None) -> None:
    host = via or REMOTE
    if host == "local":
        dst = Path.home() / remote_path
        dst.mkdir(parents=True, exist_ok=True)
        subprocess.run(["rsync", "-a", f"{local}/", f"{dst}/"], check=True)
    else:
        subprocess.run(["rsync", "-a", "-e", "ssh -o BatchMode=yes -o ConnectTimeout=30",
                        f"{local}/", f"{host}:{remote_path}/"], check=True, timeout=3600)


def rsync_from(remote_path: str, local: Path) -> None:
    local.mkdir(parents=True, exist_ok=True)
    if REMOTE == "local":
        subprocess.run(["rsync", "-a", f"{Path.home() / remote_path}/", f"{local}/"], check=True)
    else:
        subprocess.run(["rsync", "-a", "-e", "ssh -o BatchMode=yes -o ConnectTimeout=30",
                        f"{REMOTE}:{remote_path}/", f"{local}/"], check=True, timeout=3600)


def ensure_queue() -> None:
    rsh("mkdir -p " + " ".join(q(s) for s in STATES))


def notify(title: str, text: str, file: Path | None = None) -> None:
    tool = Path.home() / ".local/bin/report-notify"
    if not tool.exists():
        return
    extra = ["--file", str(file), "--no-excerpt"] if file and file.exists() else []
    try:
        p = subprocess.run([str(tool), "--tag", "agyq", "--title", title, "--text", text] + extra,
                           capture_output=True, text=True, timeout=60)
        log(f"   Telegram：{title} → {(p.stdout or p.stderr).strip()[:60] or f'exit {p.returncode}'}")
    except Exception as e:
        log(f"   Telegram 送出失敗：{e}")


def dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


# ───────────────────────── submit ─────────────────────────
def cmd_submit(a) -> int:
    base = Path(a.base).resolve()
    jid = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + re.sub(r"[^\w一-鿿-]+", "-", a.title)[:40]
    models = [m.strip() for m in (a.models or ",".join(DEFAULT_MODELS)).split(",") if m.strip()]
    with tempfile.TemporaryDirectory() as td:
        jd = Path(td) / jid
        (jd / "materials").mkdir(parents=True)
        shutil.copy(a.task, jd / "task.md")
        mats = []
        for f in a.files:
            src = Path(f).resolve()
            rel = src.relative_to(base)
            (jd / "materials" / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, jd / "materials" / rel)
            mats.append(str(rel))
        job = {"id": jid, "type": "review", "title": a.title,
               "created": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
               "models": models, "materials": mats,
               "max_rounds": a.max_rounds, "timeout_min": a.timeout_min}
        (jd / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
        ensure_queue()
        rsync_to(jd, q("inbox", jid))
    print(f"已放入佇列：{jid}（{len(mats)} 個素材，模型 {', '.join(models)}）")
    return 0


# ───────────────────────── 審查任務：提示與驗收 ─────────────────────────
OUTPUT_SPEC = """
【輸出格式】只輸出一個 ```json 程式碼區塊，區塊外不要有任何說明文字。不要使用任何工具，所有素材都已經放在上面。
```json
{
  "summary": "三到五句的整體評估",
  "findings": [
    {
      "id": "F1",
      "area": "內容正確性｜教學設計｜程式邏輯｜可用性｜無障礙｜效能｜架構｜安全｜維護性｜一致性｜用語（擇一）",
      "severity": "高｜中｜低（擇一）",
      "title": "一句話說明問題",
      "file": "問題所在的素材路徑，必須和上面標示的路徑一字不差",
      "quote": "從該檔案原文逐字複製的一段（10～200 字），用來證明問題確實存在",
      "problem": "為什麼這是問題、會造成什麼後果",
      "recommendation": "具體怎麼改"
    }
  ]
}
```
"""

CRITERIA = """1. 只有一個 ```json 區塊，可被 json.loads 解析；頂層有 summary（字串）與 findings（陣列）。
2. findings 共 3～25 條，每條都有 id、area、severity、title、file、quote、problem、recommendation。
3. area 與 severity 必須是上面列出的選項之一。
4. file 必須是素材清單裡的路徑之一。
5. quote 必須是該檔案原文中逐字存在的片段（空白字元視為相同），長度 10～200 字。
   找不到原文的發現會被退回——不要改寫、摘要或憑印象引用。
6. 只寫有原文證據支持的問題，不要推測素材裡沒有出現的東西。"""


def build_prompt(jd: Path, job: dict, only: list[str] | None = None) -> tuple[str, dict[str, str]]:
    materials = {}
    parts = [(jd / "task.md").read_text(encoding="utf-8"), "\n\n【素材】"]
    for rel in (only if only is not None else job["materials"]):
        txt = (jd / "materials" / rel).read_text(encoding="utf-8", errors="replace")
        materials[rel] = txt
        lang = rel.rsplit(".", 1)[-1] if "." in rel else ""
        parts.append(f"\n=== 檔案：{rel} ===\n```{lang}\n{txt}\n```\n")
    parts.append(OUTPUT_SPEC)
    return "".join(parts), materials


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def check_review(text: str, materials: dict[str, str]) -> tuple[bool, str, dict | None]:
    m = re.findall(r"```json\s*(.*?)```", text, re.S)
    raw = m[0] if m else text
    try:
        data = json.loads(raw)
    except Exception as e:
        return False, f"無法解析 JSON（{type(e).__name__}: {str(e)[:80]}）。請只輸出一個 ```json 區塊。", None
    if not isinstance(data, dict) or not isinstance(data.get("summary"), str) or not isinstance(data.get("findings"), list):
        return False, "頂層必須有 summary（字串）與 findings（陣列）。", None
    fs = data["findings"]
    if not 3 <= len(fs) <= 25:
        return False, f"findings 有 {len(fs)} 條，必須在 3～25 條之間。", None
    normed = {k: _norm(v) for k, v in materials.items()}
    need = ("id", "area", "severity", "title", "file", "quote", "problem", "recommendation")
    errs = []
    for f in fs:
        fid = f.get("id", "?")
        miss = [k for k in need if not str(f.get(k, "")).strip()]
        if miss:
            errs.append(f"{fid} 缺少欄位 {miss}"); continue
        if f["area"] not in AREAS:
            errs.append(f"{fid} 的 area「{f['area']}」不在選項內")
        if f["severity"] not in SEVERITIES:
            errs.append(f"{fid} 的 severity「{f['severity']}」不在選項內")
        if f["file"] not in materials:
            errs.append(f"{fid} 的 file「{f['file']}」不是素材路徑"); continue
        qn = _norm(f["quote"])
        if not 10 <= len(qn) <= 200:
            errs.append(f"{fid} 的 quote 長度 {len(qn)}，必須 10～200 字")
        elif qn not in normed[f["file"]]:
            errs.append(f"{fid} 的 quote 在 {f['file']} 找不到原文（必須逐字複製）")
    if errs:
        return False, "以下發現沒有通過驗收，請修正後重新提交完整版本：\n- " + "\n- ".join(errs[:15]), None
    return True, f"通過（{len(fs)} 條發現，全部有原文證據）", data


# ───────────────────────── run（MBP）─────────────────────────
class Defer(Exception):
    """連線或認證類失敗：整批延後、停止本輪，不重試。"""


class QuotaWait(Exception):
    """某個模型的配額組快用完：這個模型先跳過，工作留在佇列，等窗口重置再補跑（不算失敗）。"""


QUOTA_PAT = re.compile(r"resource.?exhausted|quota|rate.?limit|\b429\b", re.I)


def model_group(model: str) -> str:
    return "Gemini Models" if model.startswith("gemini") else "Claude and GPT models"


def usage_once() -> list[dict]:
    """查一次額度（0 token）。連線或認證問題 → Defer；不重試。"""
    sys.path.insert(0, str(BRIDGE))
    import agy_meter as m
    guard = _guard()
    agy = Path.home() / ".local/bin/agy"
    try:
        p = subprocess.run([str(agy), "-p", "/usage", "--output-format", "json"],
                           capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        raise Defer("額度查詢逾時（90 秒）")
    except Exception as e:
        raise Defer(f"額度查詢失敗（{type(e).__name__}）")
    out = p.stdout + "\n" + p.stderr
    buckets = m._parse_usage(p.stdout) if p.returncode == 0 else []
    if not buckets and (p.returncode == 78 or guard.looks_like_network_failure(out) or m._classify_failure(
            p.returncode, p.stdout, p.stderr) in ("未登入", "網路或服務暫時錯誤")):
        raise Defer(f"額度查詢遇到連線或認證問題（exit {p.returncode}）：{out.strip()[:120]}")
    return buckets


def group_remaining(buckets: list[dict], group: str) -> float:
    vals = [b.get("remaining_fraction", 1.0) for b in buckets if b.get("group") == group]
    return min(vals) if vals else 1.0


def _guard():
    sys.path.insert(0, str(BRIDGE))
    import agy_guard  # noqa: E402  找不到就讓 run 失敗，寧可不跑
    return agy_guard


def run_model(jd: Path, job: dict, model: str, prompt: str, materials: dict, label: str | None = None) -> dict:
    sys.path.insert(0, str(BRIDGE))
    import agy_meter as m
    guard = _guard()
    rd = jd / "results"; rd.mkdir(exist_ok=True)
    safe = (label or model).replace("/", "_")
    conv, fb = None, ""
    tmin = int(job.get("timeout_min", 60))
    group = model_group(model)
    def rem5h(bs):
        v = [b["remaining_fraction"] for b in bs if b.get("group") == group and b.get("window") == "5h"]
        return v[0] if v else None
    def used_pct():
        """這個模型在這件工作吃掉的 5h 額度（百分點）。事後量測失敗就回 None，不影響結果。"""
        try:
            a, b = start5h, rem5h(usage_once())
        except Defer:
            return None
        return round((a - b) * 100, 2) if a is not None and b is not None and a >= b else None
    # 額度只在這個模型開始前查一次、結束後查一次（2026-09-26：每回合前後都查，/usage 呼叫太密，
    # 當天家裡網路被守門程式在 15 秒內記了兩次失敗、誤列黑名單）
    before = usage_once()
    start5h = rem5h(before)
    for r in range(1, int(job.get("max_rounds", 2)) + 1):
        for b in (before if r == 1 else []):
            if b.get("group") != group:
                continue
            floor = WEEKLY_RESERVE.get(group, MIN_QUOTA) if b.get("window") == "weekly" else MIN_QUOTA
            if b.get("remaining_fraction", 1.0) < floor:
                raise QuotaWait(f"{model}：{group} {b.get('window')} 額度剩 {b['remaining_fraction']:.0%}"
                                f"（保留線 {floor:.0%}）")
        if r == 1:
            p = prompt + "\n\n【驗收條件】\n" + CRITERIA
        else:
            p = f"上一版沒有通過驗收。驗收者的意見如下，請據此修正後重新提交完整版本：\n\n{fb}"
            if "JSON" in fb or "頂層" in fb:
                # 格式整個不對（例如自己另外寫報告檔、欄位名稱自己取）：把格式規格再給一次
                p += "\n\n不要使用任何工具、不要另外建立檔案，直接在回覆裡輸出。" + OUTPUT_SPEC + "\n【驗收條件】\n" + CRITERIA
        t0 = dt.datetime.now()
        data = m.run(p, model=model, timeout=tmin * 60, measure_quota=False, conversation=conv,
                     note=f"agyq {job['id']} {label or model} r{r}", print_timeout=f"{tmin}m")
        secs = (dt.datetime.now() - t0).total_seconds()
        status = str(data.get("status") or "")
        err = str(data.get("error") or "")
        if status == "NETWORK_BLOCKED":
            raise Defer(f"{model}：網路被封鎖（{err[:80]}）")
        if status != "SUCCESS":
            # 沒有 JSON（shim 擋下、二進位檔起不來）一律當連線問題：分不出原因時寧可延後
            if not status or guard.looks_like_network_failure(err + " " + (data.get("response") or "")):
                raise Defer(f"{model}：連線或認證失敗（{status or '無回應'} {err[:100]}）")
            if status == "LOCAL_ERROR" and "timed out" not in err:
                raise Defer(f"{model}：本機呼叫失敗（{err[:100]}）")
            # 伺服器端串流中斷（不是網路被擋）：同一個對話請它接著做，算一個回合
            if "stream was interrupted" in err.lower() and data.get("conversation_id") \
                    and r < int(job.get("max_rounds", 2)):
                conv = data["conversation_id"]
                fb = "串流中斷了。請從頭輸出完整的 ```json 區塊（不要只輸出後半段）。"
                log(f"   {model} 第 {r} 回合串流中斷（伺服器端），同一對話接續")
                continue
            if QUOTA_PAT.search(err):
                raise QuotaWait(f"{model}：配額用完（{err[:80]}）")
            log(f"   {model} 第 {r} 回合狀態 {status}：{err[:120]}（非連線問題，此模型不再重試）")
            return {"model": model, "ok": False, "rounds": r, "status": status, "error": err[:300], "seconds": round(secs)}
        conv = data.get("conversation_id") or conv
        text = data.get("response") or ""
        if not text.strip() and not (data.get("usage") or {}).get("total_tokens"):
            # 2026-09-25 實測：gpt-oss-120b 遇到 13 萬字元的提示會回 SUCCESS、0 token、空字串，
            # 再送回饋也一樣是空的。多半是提示超過它的長度上限，要切小素材重送
            log(f"   {model} 第 {r} 回合回應是空的且 0 token（多半是提示太長），此模型不再重試")
            return {"model": model, "ok": False, "rounds": r, "status": "EMPTY_RESPONSE",
                    "error": f"提示 {len(prompt):,} 字元，回應空白、0 token", "seconds": round(secs)}
        (rd / f"{safe}.r{r}.md").write_text(text, encoding="utf-8")
        ok, fb, parsed = check_review(text, materials)
        log(f"   {model} 第 {r} 回合（{secs:.0f} 秒）：{'✅ ' if ok else '❌ '}{fb.splitlines()[0][:90]}")
        if ok:
            (rd / f"{safe}.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=1), encoding="utf-8")
            return {"model": model, "ok": True, "rounds": r, "status": status, "findings": len(parsed["findings"]),
                    "conversation_id": conv, "seconds": round(secs), "quota_5h_pct": used_pct(),
                    "tokens": (data.get("usage") or {}).get("total_tokens")}
    return {"model": model, "ok": False, "rounds": r, "status": "VALIDATION_FAILED", "error": fb[:300],
            "conversation_id": conv, "quota_5h_pct": used_pct()}


def execute(jd: Path) -> str:
    job = json.loads((jd / "job.json").read_text(encoding="utf-8"))
    if job.get("type") == "image":
        return execute_image(jd, job)
    if job.get("type") != "review":
        log(f"   不支援的工作類型 {job.get('type')}")
        return "failed"
    prompt, materials = build_prompt(jd, job)
    mf = jd / "manifest.json"
    man = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {"job": job["id"], "models": {}}
    log(f"   提示 {len(prompt):,} 字元，素材 {len(materials)} 個")
    for model in job["models"]:
        if man["models"].get(model, {}).get("ok"):
            log(f"   {model} 先前已完成，略過")
            continue
        limit = MODEL_MAX_CHARS.get(model)
        try:
            if limit and len(prompt) > limit:
                man["models"][model] = run_chunked(jd, job, model, limit, man)
            else:
                man["models"][model] = run_model(jd, job, model, prompt, materials)
        except QuotaWait as e:
            log(f"   ⏳ {e}，先跳過，等額度重置再補跑")
            man["models"][model] = {"model": model, "ok": False, "status": "QUOTA_WAIT", "error": str(e)}
        finally:
            mf.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    if any(man["models"].get(mm, {}).get("status") == "QUOTA_WAIT" for mm in job["models"]):
        return "waiting"
    return "done" if any(v.get("ok") for v in man["models"].values()) else "failed"


def split_materials(jd: Path, job: dict, limit: int) -> list[list[str]]:
    """依字元數把素材分組，每組連同任務說明與格式要求不超過 limit。單檔本身就超過的自成一組。"""
    overhead = len(build_prompt(jd, job, only=[])[0]) + len(CRITERIA) + 200
    groups, cur, size = [], [], overhead
    for rel in job["materials"]:
        n = len((jd / "materials" / rel).read_text(encoding="utf-8", errors="replace")) + len(rel) + 30
        if cur and size + n > limit:
            groups.append(cur); cur, size = [], overhead
        cur.append(rel); size += n
    if cur:
        groups.append(cur)
    return groups


def run_chunked(jd: Path, job: dict, model: str, limit: int, man: dict) -> dict:
    """素材太長時分份審查、各自驗收，再把通過的各份合併成一份結果。"""
    groups = split_materials(jd, job, limit)
    log(f"   {model} 提示上限 {limit:,} 字元，素材分成 {len(groups)} 份")
    parts = man.setdefault("chunks", {}).setdefault(model, {})
    for k, only in enumerate(groups, 1):
        tag = f"{model}@{k}"
        if parts.get(tag, {}).get("ok"):
            continue
        prompt, mats = build_prompt(jd, job, only=only)
        parts[tag] = run_model(jd, job, model, prompt, mats, label=tag)
    rd = jd / "results"
    merged = {"summary": "", "findings": []}
    for k in range(1, len(groups) + 1):
        f = rd / f"{model.replace('/', '_')}@{k}.json"
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            merged["summary"] += f"（第 {k} 份）{d.get('summary', '')}\n"
            merged["findings"] += d["findings"]
    ok_parts = sum(1 for v in parts.values() if v.get("ok"))
    if merged["findings"]:
        (rd / f"{model.replace('/', '_')}.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"model": model, "ok": ok_parts > 0, "chunks": len(groups), "chunks_ok": ok_parts,
            "findings": len(merged["findings"]), "status": "SUCCESS" if ok_parts == len(groups) else "PARTIAL",
            "rounds": max((v.get("rounds", 0) for v in parts.values()), default=0),
            "seconds": sum(v.get("seconds", 0) or 0 for v in parts.values())}


def write_summary(jd: Path) -> Path | None:
    """結果摘要（markdown），送回 Studio 時一起帶走，也當 Telegram 附件。"""
    job = json.loads((jd / "job.json").read_text(encoding="utf-8"))
    if job.get("type") == "image":
        return write_image_summary(jd, job)
    mf = jd / "manifest.json"
    if not mf.exists():
        return None
    man = json.loads(mf.read_text(encoding="utf-8"))
    out = [f"# {job.get('title', job['id'])}", "", f"工作 `{job['id']}`，素材 {len(job.get('materials', []))} 個", "",
           "| 模型 | 結果 | 回合 | 發現 | 秒 |", "|---|---|---|---|---|"]
    for mname, v in man["models"].items():
        out.append(f"| {mname} | {'✅' if v.get('ok') else '❌ ' + str(v.get('status'))} | {v.get('rounds', '')} "
                   f"| {v.get('findings', '')} | {v.get('seconds', '')} |")
    for mname, v in man["models"].items():
        rj = jd / "results" / f"{mname.replace('/', '_')}.json"
        if not rj.exists():
            continue
        data = json.loads(rj.read_text(encoding="utf-8"))
        out += ["", f"## {mname}", "", data.get("summary", ""), ""]
        order = {"高": 0, "中": 1, "低": 2}
        for f in sorted(data["findings"], key=lambda f: order.get(f.get("severity"), 3)):
            out.append(f"- **[{f['severity']}｜{f['area']}]** {f['title']}（`{f['file']}`）")
    out += ["", "※ 模型發現尚未經 Claude 驗證；引用原文已由程式逐字核對。"]
    p = jd / "results" / "摘要.md"
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    return p


def deliver(jd: Path, jid: str, outcome: str) -> str:
    summary = write_summary(jd)
    if summary:
        shutil.copy(summary, LOCAL_ROOT / "last_summary.md")
    bundle = jd.parent / f"{jid}.bundle"
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir()
    for name in ("job.json", "manifest.json"):
        if (jd / name).exists():
            shutil.copy(jd / name, bundle / name)
    if (jd / "results").exists():
        shutil.copytree(jd / "results", bundle / "results")
    size = dir_size(bundle)
    if size <= SMALL_MAX:
        rsync_to(bundle, q(outcome, jid))
        rsh(f"rm -rf '{q('claimed', jid)}'")
        shutil.rmtree(bundle); shutil.rmtree(jd)
        return f"已送回 {outcome}/（{size/1024:.0f} KB，網路直送）"
    OUTBOX_LARGE.mkdir(parents=True, exist_ok=True)
    dst = OUTBOX_LARGE / jid
    if dst.exists():
        shutil.rmtree(dst)
    shutil.move(str(bundle), dst)
    (dst / ".outcome").write_text(outcome, encoding="utf-8")
    rsh(f"mv '{q('claimed', jid)}' '{q('waiting-cable', jid)}' && "
        f"echo '結果 {size/1048576:.0f} MB，超過 50 MB，等下次接雷電線由 linksync 送回' > '{q('waiting-cable', jid)}/等傳輸線.txt'")
    shutil.rmtree(jd)
    return f"結果 {size/1048576:.0f} MB，已放入待傳區，等雷電線"


def quota_ok() -> tuple[bool, str]:
    """只查一次額度。agy_meter.quota() 失敗會自動重試，這裡不用它——連線失敗一律不重試。"""
    buckets = usage_once()
    if not buckets:
        return False, "額度查詢沒有資料，本輪不執行"
    groups = {b.get("group") for b in buckets}
    rem = {g: group_remaining(buckets, g) for g in groups}
    desc = "、".join(f"{g} 剩 {v:.0%}" for g, v in rem.items())
    if all(v < MIN_QUOTA for v in rem.values()):
        return False, "兩個配額組都不足：" + desc
    return True, desc


def cmd_run(a) -> int:
    LOCK.touch(exist_ok=True)
    lf = LOCK.open("w")
    try:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0                                   # 上一輪還在跑
    try:
        guard = _guard()
    except Exception as e:
        log(f"找不到 agy_guard（{e}），為了安全不執行")
        return 1
    b = guard.blocked()
    if b:
        # 在學校網域或其他封鎖網路：什麼都不做，連佇列都不看
        if a.verbose:
            log("封鎖網路，本輪不處理：" + b.splitlines()[0][:100])
        return 0
    try:
        ensure_queue()
        inbox = [x for x in rsh(f"ls -1 {q('inbox')}").stdout.split() if x]
    except Exception as e:
        log(f"連不到佇列（{e}）")
        return 1
    # 續作：上一輪延後、已完成的模型結果還留在 MBP 的工作（遠端會在 inbox 或 claimed）
    resume = {p.name for p in WORK.glob("*") if p.is_dir() and not p.name.endswith(".bundle")} if WORK.exists() else set()
    jobs = sorted(resume | set(inbox))
    if not jobs:
        return 0
    try:
        ok, why = quota_ok()
    except Defer as e:
        return _defer(None, e)
    log(f"佇列 {len(inbox)} 件、續作 {len(resume)} 件；{why}")
    if not ok:
        return 0
    for jid in jobs:
        if guard.blocked():                        # 途中換了網路（例如合上蓋子帶去學校）
            log("途中偵測到封鎖網路，本輪停止")
            return 0
        jd = WORK / jid
        try:
            if jid in inbox:
                if rsh(f"mv '{q('inbox', jid)}' '{q('claimed', jid)}'", check=False).returncode != 0:
                    continue                       # 已被領走
            if not (jd / "job.json").exists():
                rsync_from(q("claimed", jid), jd)
        except Exception as e:
            log(f"領取 {jid} 時連不到 Studio（{e}），本輪停止")
            return 1
        log(f"▶ {jid}")
        try:
            outcome = execute(jd)
        except Defer as e:
            return _defer(jid, e)
        if outcome == "waiting":
            rsh(f"mv '{q('claimed', jid)}' '{q('inbox', jid)}'", check=False)
            log(f"⏳ {jid}：部分模型等額度，已完成的結果留在 MBP，工作退回 inbox")
            continue
        try:
            msg = deliver(jd, jid, outcome)
        except Exception as e:
            log(f"送回 {jid} 失敗（{e}），結果留在 MBP，下一輪再送；本輪停止")
            return 1
        log(f"■ {jid}：{outcome}，{msg}")
        notify(f"agyq {outcome}", f"{jid}\n{msg}", LOCAL_ROOT / "last_summary.md")
    return 0


def _defer(jid: str | None, e: Exception) -> int:
    """連線或認證類失敗：整批延後、這一輪停止，不重試。通知每 6 小時最多一次。"""
    log(f"⏸ 延後：{e}。本輪停止，不重試。" + (f"{jid} 退回 inbox，已完成的模型結果保留在 MBP。" if jid else ""))
    if jid:
        rsh(f"mv '{q('claimed', jid)}' '{q('inbox', jid)}'", check=False)
    stamp = LOCAL_ROOT / ".last_defer_notice"
    if not stamp.exists() or (dt.datetime.now().timestamp() - stamp.stat().st_mtime) > 6 * 3600:
        LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
        stamp.touch()
        notify("agyq 延後", f"{jid or '（額度查詢）'}\n{e}\n下一輪（10 分鐘後）若網路正常再繼續。")
    return 0


# ───────────────────────── 生圖任務（2026-10-02） ─────────────────────────
# Studio 在學校網域不能碰 Antigravity；剪片或做教材需要圖時，Studio 用 submit-image 提出需求，
# MBP 在家時領走，交給 image_router（額度分配、備援、清單都在那裡），完成後連同 _manifest.json 送回。
# jobs.json 格式與 image_router 相同（不必寫 out_dir），control／mermaid 的路徑相對 --base。
# ⚠️ prompt 必須是自己寫的描述：不可貼新聞、網頁、使用者上傳檔的文字（generate_image 那一輪有 write_file 權限）。
ROUTER = BRIDGE / "image_router.py"
IMAGE_KINDS = {"photo_topology", "photo_object", "mindmap_blank", "icon_set", "diagram_text", "cover", "background", "chart"}
IMAGE_MAX_DAYS = 3          # 額度一直不夠時最多等三天，之後把做好的先送回，缺的列在摘要
NAME_PAT = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


def validate_image_jobs(spec: dict, base: Path) -> list[str]:
    errs, names = [], set()
    jobs = spec.get("jobs")
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= 40:
        return ["jobs 必須是 1～40 項的陣列"]
    for i, j in enumerate(jobs, 1):
        tag = f"第 {i} 項"
        n = str(j.get("name", ""))
        if not NAME_PAT.match(n):
            errs.append(f"{tag} name「{n}」只能用小寫英文、數字、底線，英文字母開頭，≤40 字")
        elif n in names:
            errs.append(f"{tag} name「{n}」重複")
        names.add(n)
        if j.get("kind") not in IMAGE_KINDS:
            errs.append(f"{tag} kind 必須是 {'、'.join(sorted(IMAGE_KINDS))} 之一")
        pr = str(j.get("prompt", ""))
        if not 10 <= len(pr) <= 500:
            errs.append(f"{tag} prompt 要 10～500 字元（目前 {len(pr)}）")
        if re.search(r"https?://|www\.", pr):
            errs.append(f"{tag} prompt 不可含網址（只能放自己寫的描述，不可貼外部內容）")
        if j.get("importance", 2) not in (1, 2, 3):
            errs.append(f"{tag} importance 只能是 1、2、3")
        sz = j.get("size", [1024, 1024])
        if not (isinstance(sz, list) and len(sz) == 2 and all(isinstance(x, int) and 256 <= x <= 2048 for x in sz)):
            errs.append(f"{tag} size 要是 [寬, 高]，各 256～2048")
        for key in ("control", "mermaid"):
            if j.get(key) and not (base / j[key]).is_file():
                errs.append(f"{tag} {key} 檔案不存在：{base / j[key]}")
    return errs


def cmd_submit_image(a) -> int:
    base = Path(a.base).resolve()
    spec = json.loads(Path(a.jobs).read_text(encoding="utf-8"))
    errs = validate_image_jobs(spec, base)
    if errs:
        print("需求檔有問題，沒有放入佇列：\n  " + "\n  ".join(errs))
        return 2
    jid = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-圖-" + re.sub(r"[^\w一-鿿-]+", "-", a.title)[:36]
    with tempfile.TemporaryDirectory() as td:
        jd = Path(td) / jid
        (jd / "materials").mkdir(parents=True)
        mats = []
        for j in spec["jobs"]:
            for key in ("control", "mermaid"):
                if j.get(key):
                    rel = Path(j[key]).as_posix().lstrip("/")
                    (jd / "materials" / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(base / j[key], jd / "materials" / rel)
                    j[key] = rel; mats.append(rel)
        spec.pop("out_dir", None)
        spec["urgent"] = bool(a.urgent or spec.get("urgent"))
        (jd / "images.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        job = {"id": jid, "type": "image", "title": a.title,
               "created": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
               "count": len(spec["jobs"]), "urgent": spec["urgent"], "materials": mats}
        (jd / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
        ensure_queue()
        rsync_to(jd, q("inbox", jid))
    print(f"已放入佇列：{jid}（{len(spec['jobs'])} 張{'，急件' if spec['urgent'] else ''}）。"
          f"MBP 在家時每 10 分鐘領一次，完成後放在 ~/{q('done', jid)}/results/ 並送 Telegram。")
    return 0


def _new_failures(since: float) -> list[str]:
    fd = Path.home() / ".gemini/agy-guard/failures"
    out = []
    for f in fd.glob("*.txt") if fd.exists() else []:
        if f.stat().st_mtime >= since:
            out.append(f.read_text(encoding="utf-8", errors="replace")[:400])
    return out


def execute_image(jd: Path, job: dict) -> str:
    guard = _guard()
    spec = json.loads((jd / "images.json").read_text(encoding="utf-8"))
    rd = jd / "results"; rd.mkdir(exist_ok=True)
    for j in spec["jobs"]:
        for key in ("control", "mermaid"):
            if j.get(key):
                j[key] = str(jd / "materials" / j[key])
    spec["out_dir"] = str(rd)
    run_spec = jd / "_router_jobs.json"
    run_spec.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    t0 = dt.datetime.now().timestamp()
    log(f"   生圖 {len(spec['jobs'])} 張{'（急件）' if spec.get('urgent') else ''}，交給 image_router")
    p = subprocess.run([sys.executable, str(ROUTER), "run", str(run_spec)] + (["--urgent"] if spec.get("urgent") else []),
                       capture_output=True, text=True, timeout=4 * 3600)
    with (rd / "_router.log").open("a", encoding="utf-8") as f:
        f.write(f"\n===== {dt.datetime.now():%F %T} rc={p.returncode} =====\n{p.stdout}\n{p.stderr[-3000:]}\n")
    # 中途登入失效或網路被擋：image_router 會默默改走本機備援。這種情況整件延後，
    # 不把本機補畫的圖當成品送回（下一輪已存在的檔案會被跳過，所以先刪掉這一輪本機補的）
    bad = [t for t in _new_failures(t0)
           if re.search(r"Authentication required|log in", t, re.I) or guard.looks_like_network_failure(t)]
    mp = rd / "_manifest.json"
    man = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    if bad:
        for n, v in list(man.items()):
            if v.get("tool") != "agy":
                if v.get("file") and Path(v["file"]).exists():
                    Path(v["file"]).unlink()
                man.pop(n)
        mp.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        raise Defer("生圖途中 Antigravity 連線或登入失敗：" + bad[0].splitlines()[-1][:100])
    if p.returncode != 0 and not man:
        log(f"   image_router 失敗：{p.stderr[-300:]}")
        return "failed"
    missing = [j["name"] for j in spec["jobs"] if not (man.get(j["name"]) or {}).get("file")]
    age_days = (dt.datetime.now().astimezone() - dt.datetime.fromisoformat(job["created"])).days
    if missing and age_days < IMAGE_MAX_DAYS and not spec.get("urgent"):
        log(f"   還缺 {len(missing)} 張（{'、'.join(missing[:6])}），等額度重置後再補")
        return "waiting"
    return "done" if len(missing) < len(spec["jobs"]) else "failed"


def write_image_summary(jd: Path, job: dict) -> Path | None:
    rd = jd / "results"
    spec = json.loads((jd / "images.json").read_text(encoding="utf-8"))
    man = json.loads((rd / "_manifest.json").read_text(encoding="utf-8")) if (rd / "_manifest.json").exists() else {}
    tool_name = {"agy": "Antigravity", "flux2_t2i": "本機 FLUX.2", "flux2_edit": "本機 FLUX.2 參考圖編輯",
                 "zimage_t2i": "本機 Z-Image", "program": "程式繪製", "defer": "未產出"}
    out = [f"# {job.get('title', job['id'])}", "", f"工作 `{job['id']}`，共 {len(spec['jobs'])} 張", "",
           "| 檔名 | 種類 | 工具 | 檔案 | 備註 |", "|---|---|---|---|---|"]
    for j in spec["jobs"]:
        v = man.get(j["name"]) or {}
        f = Path(v["file"]).name if v.get("file") else "（未產出）"
        note = []
        if v.get("must_check_wiring") and v.get("file"):
            note.append("接線要逐項驗收")
        if v.get("redo_after_reset"):
            note.append("額度重置後應改用 Antigravity 重生")
        if v.get("tool") == "defer" or not v.get("file"):
            note.append(str(v.get("note") or v.get("reason") or "額度不足"))
        out.append(f"| {j['name']} | {j['kind']} | {tool_name.get(v.get('tool'), v.get('tool') or '—')} | {f} | {'；'.join(note)} |")
    if (rd / "_program_todo.md").exists():
        out += ["", "## 需要程式繪製（Studio 自己畫）", "", (rd / "_program_todo.md").read_text(encoding="utf-8")]
    out += ["", "※ 驗收一律人工逐項看：有字的圖逐字比對、接線圖逐條核對（/Volumes/Work/圖片產生規範.md）。",
            "※ Antigravity 生成的圖存成 JPG；作者／授權欄位寫「AI 生成（Google Antigravity generate_image）」。"]
    pth = rd / "摘要.md"
    pth.write_text("\n".join(out) + "\n", encoding="utf-8")
    return pth


# ───────────────────────── 其他子命令 ─────────────────────────
def cmd_status(a) -> int:
    ensure_queue()
    for s in STATES:
        items = [x for x in rsh(f"ls -1 {q(s)}").stdout.split() if x]
        print(f"{s:<14} {len(items):>3} 件" + ("：" + "、".join(items[-5:]) if items else ""))
    if OUTBOX_LARGE.exists() and any(OUTBOX_LARGE.iterdir()):
        print(f"MBP 待傳區      {len(list(OUTBOX_LARGE.iterdir())):>3} 件")
    return 0


def cmd_deliver_large(a) -> int:
    """linksync 在接上雷電線時呼叫：把待傳區送到 Studio，核對後刪除。"""
    if not OUTBOX_LARGE.exists():
        return 0
    rc = 0
    for d in sorted(p for p in OUTBOX_LARGE.iterdir() if p.is_dir()):
        outcome = (d / ".outcome").read_text().strip() if (d / ".outcome").exists() else "done"
        try:
            rsync_to(d, q(outcome, d.name), via=a.via)
            cnt = sum(1 for f in d.rglob("*") if f.is_file())
            chk = subprocess.run(["ssh", "-o", "BatchMode=yes", a.via,
                                  f"find {q(outcome, d.name)} -type f | wc -l"],
                                 capture_output=True, text=True, timeout=60).stdout.strip()
            if str(cnt) != chk:
                raise RuntimeError(f"檔案數不符：本機 {cnt}、Studio {chk}")
            subprocess.run(["ssh", "-o", "BatchMode=yes", a.via, f"rm -rf '{q('waiting-cable', d.name)}'"],
                           timeout=60)
            shutil.rmtree(d)
            log(f"雷電線送達：{d.name}（{cnt} 檔）")
        except Exception as e:
            log(f"雷電線送回失敗：{d.name}：{e}")
            rc = 1
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(prog="agyq", description=__doc__.split("\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("submit")
    s.add_argument("--title", required=True)
    s.add_argument("--task", required=True, help="任務說明（markdown）")
    s.add_argument("--base", required=True, help="素材路徑的相對基準")
    s.add_argument("--models", default=None)
    s.add_argument("--max-rounds", type=int, default=3)
    s.add_argument("--timeout-min", type=int, default=60)
    s.add_argument("files", nargs="+")
    si = sp.add_parser("submit-image", help="提出生圖需求（Studio 用）")
    si.add_argument("--title", required=True)
    si.add_argument("--jobs", required=True, help="images.json（image_router 格式，見 image_router.py 說明）")
    si.add_argument("--base", default=".", help="control／mermaid 路徑的相對基準")
    si.add_argument("--urgent", action="store_true", help="急件：全部這次做完為先（額度不足時本機硬畫）")
    r = sp.add_parser("run"); r.add_argument("-v", "--verbose", action="store_true")
    sp.add_parser("status")
    d = sp.add_parser("deliver-large"); d.add_argument("--via", default="studio-tb")
    a = ap.parse_args()
    return {"submit": cmd_submit, "submit-image": cmd_submit_image, "run": cmd_run, "status": cmd_status,
            "deliver-large": cmd_deliver_large}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
