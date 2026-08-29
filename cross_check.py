#!/usr/bin/env python3
"""同一個主張丟給不同模型家族，比對結論。每次呼叫自動記進 ledger.jsonl。

用法：./cross_check.py "要驗證的主張" [模型1 模型2 ...]
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import agy_meter

HERE = Path(__file__).resolve().parent
SCHEMA = HERE / "verdict_schema.json"
DEFAULT = ["gemini-3.7-flash-high", "claude-opus-4-6-thinking", "gpt-oss-120b-medium"]


def ask(claim: str, model: str) -> tuple[str, dict]:
    d = agy_meter.run(
        f"請判斷以下主張是否成立，並指出最容易被忽略的前提。主張：{claim}",
        model=model, schema=str(SCHEMA), measure_quota=True,
    )
    return model, d


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(f"用法：{sys.argv[0]} \"主張\" [模型...]")
    claim = sys.argv[1]
    models = sys.argv[2:] or DEFAULT

    with ThreadPoolExecutor(max_workers=len(models)) as ex:
        results = list(ex.map(lambda m: ask(claim, m), models))

    verdicts, total = set(), 0
    for model, d in results:
        s = d.get("structured_output") or {}
        total += (d.get("usage") or {}).get("total_tokens", 0)
        v = s.get("verdict", "失敗")
        verdicts.add(v)
        print(f"\n── {model}")
        print(f"   判定: {v}  (信心 {s.get('confidence', '?')})")
        print(f"   理由: {s.get('reason', d.get('status', ''))}")
        print(f"   易忽略: {s.get('caveat', '')}")

    verdicts.discard("失敗")
    print()
    if len(verdicts) > 1:
        print("⚠️  結論分歧 → " + " / ".join(verdicts) + "　←這種時候才值得你親自看")
    else:
        print(f"✅ 一致: {verdicts.pop() if verdicts else '無結果'}")
    print(f"   本次 {total:,} tokens，已記入 ledger.jsonl（跑 token_report.py 看剩餘額度）")


if __name__ == "__main__":
    main()
