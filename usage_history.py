#!/usr/bin/env python3
"""長期用量追蹤：把三個來源合成每日時序表，並輸出 CSV。

三個來源的性質不同，處理方式也不同：
- quota_history.csv：額度百分比的瞬時快照（由選單列小工具每 5 分鐘取樣）。
  「當日消耗」不能用頭尾相減——中間會重置。要把相鄰樣本的**下降量**加總，
  上升代表窗口重置，直接略過。
- ledger.jsonl：每次透過 agy_meter.run() 派工的實際 token 與配額成本。
- Claude transcripts：已完整落地在 ~/.claude/projects，可隨時回溯重算，不需取樣。
"""

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import agy_meter
import claude_meter

BASE = Path(__file__).resolve().parent
OUT = BASE / "usage_history.csv"
COLS = ["date", "agy_calls", "agy_tokens", "gemini_quota_used_pct",
        "tp_quota_used_pct", "quota_samples", "claude_calls",
        "claude_billable_tokens", "claude_cache_read_tokens"]


def quota_consumed_by_day() -> dict[str, dict]:
    """從快照序列還原每日實際消耗的配額百分點（重置不計為消耗）。"""
    out: dict[str, dict] = defaultdict(
        lambda: {"gemini": 0.0, "tp": 0.0, "samples": 0})
    if not agy_meter.QUOTA_CSV.exists():
        return out

    prev = None
    with agy_meter.QUOTA_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                ts = datetime.fromisoformat(row["ts"])
                g, t = float(row["gemini_5h"]), float(row["tp_5h"])
            except (ValueError, KeyError):
                continue
            day = ts.date().isoformat()
            out[day]["samples"] += 1
            if prev:
                # 只累計下降量；上升＝窗口重置，不是負消耗
                out[day]["gemini"] += max(prev[0] - g, 0.0)
                out[day]["tp"] += max(prev[1] - t, 0.0)
            prev = (g, t)
    return out


def agy_by_day() -> dict[str, dict]:
    out: dict[str, dict] = defaultdict(lambda: {"calls": 0, "tokens": 0})
    for e in agy_meter.ledger():
        try:
            day = datetime.fromisoformat(e["ts"]).date().isoformat()
        except (ValueError, KeyError):
            continue
        out[day]["calls"] += 1
        out[day]["tokens"] += (e.get("usage") or {}).get("total_tokens", 0)
    return out


def claude_by_day(days: int) -> dict[str, dict]:
    since = datetime.now().astimezone() - timedelta(days=days)
    out: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "billable": 0, "cache_read": 0})
    for c in claude_meter.calls(since=since):
        day = c["ts"].date().isoformat()
        out[day]["calls"] += 1
        out[day]["billable"] += (c["input_tokens"] + c["cache_creation_tokens"]
                                 + c["output_tokens"])
        out[day]["cache_read"] += c["cache_read_tokens"]
    return out


def main() -> None:
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    q, a, c = quota_consumed_by_day(), agy_by_day(), claude_by_day(days)

    rows = []
    for day in sorted(set(q) | set(a) | set(c)):
        rows.append({
            "date": day,
            "agy_calls": a[day]["calls"] if day in a else 0,
            "agy_tokens": a[day]["tokens"] if day in a else 0,
            "gemini_quota_used_pct": round(q[day]["gemini"], 3) if day in q else "",
            "tp_quota_used_pct": round(q[day]["tp"], 3) if day in q else "",
            "quota_samples": q[day]["samples"] if day in q else 0,
            "claude_calls": c[day]["calls"] if day in c else 0,
            "claude_billable_tokens": c[day]["billable"] if day in c else 0,
            "claude_cache_read_tokens": c[day]["cache_read"] if day in c else 0,
        })

    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)

    print(f"【長期用量追蹤】{len(rows)} 天　→　{OUT}\n")
    print(f"{'日期':<12}{'AGY次':>6}{'AGY tok':>10}{'Gem配額%':>10}"
          f"{'3P配額%':>9}{'樣本':>5}{'CC次':>6}{'CC計費tok':>12}")
    for r in rows:
        g = f"{r['gemini_quota_used_pct']}" if r["quota_samples"] else "—"
        t = f"{r['tp_quota_used_pct']}" if r["quota_samples"] else "—"
        print(f"{r['date']:<12}{r['agy_calls']:>6}{r['agy_tokens']:>10,}"
              f"{g:>10}{t:>9}{r['quota_samples']:>5}"
              f"{r['claude_calls']:>6}{r['claude_billable_tokens']:>12,}")

    if rows and rows[-1]["quota_samples"] < 12:
        print("\n※ 配額欄位需要選單列小工具持續執行才有樣本（每 5 分鐘一筆，"
              "一天完整約 288 筆）。樣本數太少時「配額%」會低估。")


if __name__ == "__main__":
    main()
