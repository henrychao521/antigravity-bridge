"""用 8/29 同一套 FeatureScript 題目（有實測標準答案）測指定模型，結果另存，不覆蓋原本三家的 raw.json。

用法：python3 run_bench_model.py gemini-3.8-flash-high [其他模型 …]
先跑 `agy models` 確認模型 id；網路在 agy 黑名單上時 agy_meter 會直接拒絕。
評分：python3 score_model.py raw_<模型>.json（沿用 score.py 的標準答案與判準）
"""
import json, sys, time, pathlib
sys.path.insert(0, "/Users/Shared/antigravity-bridge")
import agy_meter as m
HERE = pathlib.Path(__file__).resolve().parent
prompt = (HERE / "quiz.txt").read_text()
for model in sys.argv[1:]:
    t0 = time.time()
    d = m.run(prompt, model=model, schema=str(HERE / "quiz_schema.json"), timeout=1800, measure_quota=True)
    s = d.get("structured_output") or {}
    out = {model: {"answers": s.get("answers", []), "status": d.get("status"), "secs": round(time.time() - t0, 1),
                   "tokens": (d.get("usage") or {}).get("total_tokens"), "quota_delta": d.get("quota_delta_pct"), "error": d.get("error")}}
    (HERE / f"raw_{model}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{model}: {d.get('status')} · {out[model]['secs']}s · {len(out[model]['answers'])} 題 · tokens {out[model]['tokens']} · 配額 {out[model]['quota_delta']}")
