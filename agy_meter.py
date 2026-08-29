"""Antigravity (AGY) 用量與額度採集模組 (agy_meter.py)

此模組提供 Antigravity 側的 API 呼叫次數、Token 消耗量以及配額狀態採集功能，
僅使用 Python 3.12 標準函式庫，適用於多平台整合用量報表。
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess


def quota() -> list[dict]:
    """取得 Antigravity 當前配額狀態。

    透過執行 `~/.local/bin/agy -p "/usage" --output-format json` 取得配額資訊。
    若執行失敗、逾時或檔案不存在，皆安全回傳空串列，不拋出例外。

    Returns:
        list[dict]: 攤平後的配額清單，每筆包含 group, bucket_id, window,
                    remaining_fraction, reset_time, used_pct 等欄位。
    """
    agy_bin = Path.home() / ".local" / "bin" / "agy"
    if not agy_bin.exists():
        return []

    try:
        proc = subprocess.run(
            [str(agy_bin), "-p", "/usage", "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        stdout = proc.stdout

        # 尋找第一個 '{' 與最後一個 '}'，過濾可能夾雜的警告文字
        start_idx = stdout.find("{")
        end_idx = stdout.rfind("}")
        if start_idx == -1 or end_idx == -1 or start_idx > end_idx:
            return []

        json_str = stdout[start_idx : end_idx + 1]
        data = json.loads(json_str)

        # 解析 command.data.groups
        groups = data.get("command", {}).get("data", {}).get("groups", [])
        if not isinstance(groups, list):
            return []

        results: list[dict] = []
        for g in groups:
            group_name = g.get("group") or g.get("name") or "unknown"
            # 支援巢狀 buckets 或扁平結構
            buckets = g.get("buckets") or g.get("limits") or [g]
            if not isinstance(buckets, list):
                buckets = [buckets]

            for b in buckets:
                try:
                    rem_frac = float(b.get("remaining_fraction", 0.0))
                except (ValueError, TypeError):
                    rem_frac = 0.0

                # 解析 ISO 重設時間，處理結尾 'Z' (轉為 +00:00)
                reset_raw = b.get("reset_time")
                reset_dt: datetime | None = None
                if isinstance(reset_raw, str) and reset_raw:
                    clean_ts = reset_raw.rstrip()
                    if clean_ts.endswith("Z"):
                        clean_ts = clean_ts[:-1] + "+00:00"
                    try:
                        reset_dt = datetime.fromisoformat(clean_ts)
                    except ValueError:
                        reset_dt = None
                elif isinstance(reset_raw, (int, float)):
                    reset_dt = datetime.fromtimestamp(reset_raw, tz=timezone.utc)

                used_pct = round((1.0 - rem_frac) * 100, 2)

                results.append(
                    {
                        "group": g.get("group", group_name),
                        "bucket_id": b.get("bucket_id", b.get("id", "")),
                        "window": b.get("window", ""),
                        "remaining_fraction": rem_frac,
                        "reset_time": reset_dt,
                        "used_pct": used_pct,
                    }
                )

        return results
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
        timeout: int = 600, measure_quota: bool = True) -> dict:
    """呼叫 agy 並把用量記進 ledger.jsonl。所有派工都應該走這裡。

    measure_quota=True 時，呼叫前後各拍一次額度快照（查詢本身 0 token），
    據此算出「這一次呼叫吃掉幾 % 配額」——這是推估剩餘可用次數的唯一可靠依據。
    """
    agy_bin = Path.home() / ".local" / "bin" / "agy"
    before = _quota_map() if measure_quota else {}
    started = datetime.now().astimezone()

    cmd = [str(agy_bin), "-p", prompt, "--output-format", "json"]
    if model:
        cmd += ["--model", model]
    if schema:
        cmd += ["--json-schema", schema]

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
    }
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return data


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
