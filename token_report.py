#!/usr/bin/env python3
"""Antigravity × Claude 雙邊用量計量報表。

目的不是記帳，是回答一個問題：**現在還能派給 Antigravity 什麼工作。**
所以重點在把「剩餘 % 配額」換算成「還能跑幾次這種呼叫」。
"""

import sys
from datetime import datetime, timedelta

import agy_meter
import claude_meter

# 模型 id → 配額群組的 bucket 前綴
GEMINI, THIRD_PARTY = "gemini", "3p"


def bucket_prefix(model: str) -> str:
    m = (model or "").lower()
    if m.startswith("claude") or m.startswith("gpt"):
        return THIRD_PARTY
    return GEMINI


def cost_per_call(entries: list[dict]) -> dict[str, dict]:
    """從帳本的額度差值，算出每個模型每次呼叫平均吃掉幾個百分點。"""
    acc: dict[str, dict] = {}
    for e in entries:
        d = e.get("quota_delta_pct") or {}
        model = e.get("model", "?")
        pref = bucket_prefix(model)
        five_h = d.get(f"{pref}-5h")
        if five_h is None:
            continue
        a = acc.setdefault(model, {"n": 0, "pct_5h": 0.0, "pct_weekly": 0.0,
                                   "tokens": 0, "prefix": pref})
        a["n"] += 1
        a["pct_5h"] += max(five_h, 0.0)
        a["pct_weekly"] += max(d.get(f"{pref}-weekly", 0.0), 0.0)
        a["tokens"] += (e.get("usage") or {}).get("total_tokens", 0)
    for a in acc.values():
        a["avg_5h"] = a["pct_5h"] / a["n"]
        a["avg_weekly"] = a["pct_weekly"] / a["n"]
        a["avg_tokens"] = a["tokens"] // a["n"]
    return acc


def main() -> None:
    hours = 24
    if len(sys.argv) > 1:
        try:
            hours = int(sys.argv[1])
        except ValueError:
            pass
    since = datetime.now().astimezone() - timedelta(hours=hours)

    print("=" * 68)
    print(f"  雙邊用量計量報表　（統計區間：近 {hours} 小時）")
    print("=" * 68)

    # ── Antigravity：剩餘配額 ──
    q = agy_meter.quota()
    print("\n▌ANTIGRAVITY 剩餘配額（走 Google AI Pro 訂閱，不計費）")
    if not q:
        print("  取不到——agy 未安裝或未登入")
    now = datetime.now().astimezone()
    remain = {}
    for b in q:
        remain[b["bucket_id"]] = b["remaining_fraction"] * 100
        left = b["reset_time"].astimezone() - now if b["reset_time"] else None
        eta = f"{int(left.total_seconds() // 3600)}h{int(left.total_seconds() % 3600 // 60):02d}m 後重置" if left else "?"
        bar = "█" * round(b["remaining_fraction"] * 20)
        print(f"  {b['group']:<22} {b['window']:<7} {bar:<20} "
              f"剩 {b['remaining_fraction']*100:5.1f}%  {eta}")

    # ── Antigravity：每次呼叫的實際成本與可跑次數 ──
    entries = agy_meter.ledger()
    recent = [e for e in entries
              if datetime.fromisoformat(e["ts"]) >= since]
    print(f"\n▌ANTIGRAVITY 帳本（{len(recent)} 次呼叫 / 歷來 {len(entries)} 次）")
    costs = cost_per_call(entries)
    if not costs:
        print("  尚無帶額度差值的樣本——請用 agy_meter.run() 發話以累積校準資料")
    else:
        print(f"  {'模型':<28}{'次數':>4}{'平均tok':>9}{'吃掉5h%':>9}{'還能跑':>8}")
        for model, a in sorted(costs.items(), key=lambda kv: -kv[1]["avg_5h"]):
            r = remain.get(f"{a['prefix']}-5h", 0)
            left = "充裕" if a["avg_5h"] <= 0.001 else f"{int(r / a['avg_5h'])} 次"
            print(f"  {model:<28}{a['n']:>4}{a['avg_tokens']:>9,}"
                  f"{a['avg_5h']:>9.2f}{left:>8}")
        print("  ※「還能跑」= 目前 5 小時窗口剩餘 ÷ 該模型每次平均消耗")

    # ── Claude 側 ──
    cs = claude_meter.summary(since=since)
    print(f"\n▌CLAUDE CODE 消耗（無剩餘額度可查，只記消耗）")
    for model, m in sorted(cs["by_model"].items(), key=lambda kv: -kv[1]["billable_tokens"]):
        if not m["calls"]:
            continue
        print(f"  {model:<28}{m['calls']:>4} 次  計費 {m['billable_tokens']:>10,} tok"
              f"  快取讀取 {m['cache_read_tokens']:>12,}")
    print(f"  合計 {cs['total_calls']} 次呼叫")

    # ── 派工建議 ──
    print("\n▌派工判讀")
    g5, t5 = remain.get("gemini-5h", 0), remain.get("3p-5h", 0)
    if g5 > 50:
        print(f"  ✅ Gemini 組剩 {g5:.0f}%：批量、機械性、可容錯的工作儘量丟過去")
    else:
        print(f"  ⚠️  Gemini 組只剩 {g5:.0f}%：暫緩批量派工")
    if t5 > 50:
        print(f"  ✅ Claude/GPT 組剩 {t5:.0f}%：留給需要異家族觀點的交叉驗證")
    else:
        print(f"  ⚠️  Claude/GPT 組只剩 {t5:.0f}%：交叉驗證改用純 Gemini 組，或等重置")
    print("=" * 68)


if __name__ == "__main__":
    main()
