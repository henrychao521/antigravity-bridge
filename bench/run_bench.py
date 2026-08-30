import json, subprocess, sys, time, pathlib, concurrent.futures as cf
sys.path.insert(0, "/Users/Shared/antigravity-bridge")
import agy_meter as m

MODELS = ["gemini-3.7-flash-high", "gemini-3.1-pro-high", "claude-opus-4-6-thinking"]
HERE = pathlib.Path(__file__).resolve().parent
prompt = (HERE / "quiz.txt").read_text()

def one(model):
    t0 = time.time()
    d = m.run(prompt, model=model, schema=str(HERE / "quiz_schema.json"),
              timeout=1800, measure_quota=True)
    return model, d, round(time.time() - t0, 1)

with cf.ThreadPoolExecutor(max_workers=3) as ex:
    results = list(ex.map(one, MODELS))

out = {}
for model, d, secs in results:
    s = d.get("structured_output") or {}
    out[model] = {"answers": s.get("answers", []), "status": d.get("status"),
                  "secs": secs, "tokens": (d.get("usage") or {}).get("total_tokens")}
    print(f"{model}: {d.get('status')} · {secs}s · {len((s.get('answers') or []))} 題作答")
(HERE / "raw.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
