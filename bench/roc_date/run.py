"""民國日期轉換寫程式題：依序讓各模型作答，存成 out_<模型>.py 並跑隱藏測試。
用法：python3 run.py 模型1 [模型2 …]"""
import json, re, subprocess, sys, time, pathlib
sys.path.insert(0, "/Users/Shared/antigravity-bridge")
import agy_meter as m
HERE = pathlib.Path(__file__).resolve().parent
prompt = (HERE / "task.txt").read_text(encoding="utf-8")
res = {}
for model in sys.argv[1:]:
    t0 = time.time()
    d = m.run(prompt, model=model, schema=str(HERE / "schema.json"), timeout=1200, note="bench roc_date")
    so = d.get("structured_output") or {}
    code = so.get("code") if isinstance(so, dict) else None
    if not code:   # 退而求其次：從回覆抓程式碼區塊
        mm = re.search(r"```(?:python)?\n(.*?)```", d.get("response") or "", re.S)
        code = mm.group(1) if mm else ""
    f = HERE / f"out_{model}.py"; f.write_text(code, encoding="utf-8")
    t = json.loads(subprocess.run([sys.executable, "-I", str(HERE / "hidden_tests.py"), str(f)],
                                  capture_output=True, text=True, timeout=120).stdout or "{}")
    res[model] = {"status": d.get("status"), "secs": round(time.time() - t0, 1),
                  "tokens": (d.get("usage") or {}).get("total_tokens"), "quota": d.get("quota_delta_pct"),
                  "passed": t.get("passed"), "total": t.get("total"), "fails": t.get("fails"), "load_error": t.get("load_error")}
    print(model, res[model]["status"], f'{t.get("passed")}/{t.get("total")}', res[model]["secs"], "s", flush=True)
    (HERE / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
