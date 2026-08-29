"""Claude Code 側的用量採集模組。

資料源：~/.claude/projects/<專案 slug>/<session>.jsonl
每行 assistant 訊息帶 message.usage，欄位比 Antigravity 細（分開記快取建立/讀取）。
Claude 這邊沒有可查詢的剩餘額度 API，所以只統計消耗，不推估剩餘。
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path.home() / ".claude" / "projects"


def calls(since: datetime | None = None, project: str | None = None) -> list[dict]:
    """掃出每一次 Claude API 呼叫的用量。以 requestId 去重（重試會重複寫入）。"""
    if not ROOT.exists():
        return []
    seen: set[str] = set()
    out: list[dict] = []

    dirs = [ROOT / project] if project else [d for d in ROOT.iterdir() if d.is_dir()]
    for d in dirs:
        for f in d.glob("*.jsonl"):
            try:
                fh = f.open("r", encoding="utf-8", errors="ignore")
            except OSError:
                continue
            with fh:
                for line in fh:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = rec.get("message") or {}
                    u = msg.get("usage")
                    if not isinstance(u, dict):
                        continue
                    rid = rec.get("requestId") or rec.get("uuid") or ""
                    if rid and rid in seen:
                        continue
                    if rid:
                        seen.add(rid)
                    try:
                        ts = datetime.fromisoformat(
                            rec["timestamp"].replace("Z", "+00:00")
                        ).astimezone()
                    except (KeyError, ValueError, AttributeError):
                        continue
                    if since and ts < since:
                        continue
                    out.append({
                        "ts": ts,
                        "project": d.name,
                        "session": f.stem,
                        "model": msg.get("model", "?"),
                        "input_tokens": u.get("input_tokens", 0),
                        "cache_creation_tokens": u.get("cache_creation_input_tokens", 0),
                        "cache_read_tokens": u.get("cache_read_input_tokens", 0),
                        "output_tokens": u.get("output_tokens", 0),
                        "thinking_tokens": (u.get("output_tokens_details") or {}).get("thinking_tokens", 0),
                    })
    return out


def summary(since: datetime | None = None, project: str | None = None) -> dict:
    """依模型彙總。billable = 未命中快取的輸入 + 快取建立 + 輸出（快取讀取另計，單價低很多）。"""
    rows = calls(since, project)
    by_model: dict[str, dict] = {}
    for c in rows:
        m = by_model.setdefault(c["model"], {
            "calls": 0, "input_tokens": 0, "cache_creation_tokens": 0,
            "cache_read_tokens": 0, "output_tokens": 0, "thinking_tokens": 0,
        })
        m["calls"] += 1
        for k in ("input_tokens", "cache_creation_tokens", "cache_read_tokens",
                  "output_tokens", "thinking_tokens"):
            m[k] += c[k]
    for m in by_model.values():
        m["billable_tokens"] = (m["input_tokens"] + m["cache_creation_tokens"]
                                + m["output_tokens"])
    return {
        "by_model": by_model,
        "total_calls": len(rows),
        "window_start": since.isoformat() if since else None,
    }


if __name__ == "__main__":
    s = summary(since=datetime.now().astimezone() - timedelta(days=1))
    print("【Claude Code 近 24 小時用量】")
    for model, m in sorted(s["by_model"].items(), key=lambda kv: -kv[1]["billable_tokens"]):
        print(f"  {model}: {m['calls']} 次, 計費 {m['billable_tokens']:,} tok "
              f"(快取讀取另 {m['cache_read_tokens']:,}, 思考 {m['thinking_tokens']:,})")
    print(f"  總呼叫 {s['total_calls']} 次")
