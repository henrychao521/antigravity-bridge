"""roc_to_iso 隱藏測試：不給受測模型看。用法：python3 hidden_tests.py 程式檔.py → 印出 通過/總數 與失敗清單。"""
import importlib.util, json, signal, sys
CASES = [
    ("民國115年10月14日", "2026-10-14"), ("115年10月14日", "2026-10-14"), ("  115/10/14  ", "2026-10-14"),
    ("115.10.14", "2026-10-14"), ("115-10-14", "2026-10-14"), ("115/01/05", "2026-01-05"),
    ("0115/01/05", "2026-01-05"), ("１１５／１０／１４", "2026-10-14"), ("１１５年１月５日", "2026-01-05"),
    ("一一五年十月十四日", "2026-10-14"), ("一百一十五年十月十四日", "2026-10-14"), ("民國元年一月一日", "1912-01-01"),
    ("民國元年1月1日", "1912-01-01"), ("1/1/1", "1912-01-01"), ("八十九年二月二十九日", "2000-02-29"),
    ("113/02/29", "2024-02-29"), ("民國一〇五年十二月三十一日", "2016-12-31"), ("九十年十一月三十日", "2001-11-30"),
    ("一百年一月一日", "2011-01-01"), ("民國二十年五月二十日", "1931-05-20"),
    ("112/02/29", None), ("113/04/31", None), ("115/13/01", None), ("115/00/10", None), ("115/10/00", None),
    ("0/1/1", None), ("民國0年1月1日", None), ("民國前1年1月1日", None), ("-1/1/1", None), ("", None),
    ("115/10", None), ("115年10月", None), ("115/10-14", None), ("hello", None), ("115/10/14/1", None),
    ("一百一十五年十三月一日", None), ("189/02/29", None),  # 189→2100，不是閏年
]
def main(path):
    spec = importlib.util.spec_from_file_location("cand", path); mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod); f = mod.roc_to_iso
    except Exception as e:
        print(json.dumps({"passed": 0, "total": len(CASES), "load_error": repr(e)}, ensure_ascii=False)); return
    fails = []
    signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError()))
    for inp, want in CASES:
        signal.alarm(2)
        try: got = f(inp)
        except BaseException as e: got = f"EXC:{type(e).__name__}"
        finally: signal.alarm(0)
        if got != want: fails.append({"in": inp, "want": want, "got": got})
    print(json.dumps({"passed": len(CASES) - len(fails), "total": len(CASES), "fails": fails}, ensure_ascii=False))
main(sys.argv[1])
