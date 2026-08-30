# -*- coding: utf-8 -*-
"""主管模式示範：驗收條件是「程式碼真的跑得過測試」，不是「看起來對」。"""
import re, subprocess, sys, tempfile, pathlib
sys.path.insert(0, "/Users/Shared/antigravity-bridge")
import agy_meter as m

TASK = """寫一個 Python 函式 `iso_week_range(year, week)`，回傳該 ISO 週的
(星期一日期, 星期日日期)，兩者都是 datetime.date。只用標準函式庫。
只輸出一個 ```python 區塊，不要解說。"""

CRITERIA = """必須通過以下所有測試（我會實際執行）：
1. iso_week_range(2026, 1) == (date(2025,12,29), date(2026,1,4))
2. iso_week_range(2026, 36) == (date(2026,8,31), date(2026,9,6))
3. iso_week_range(2021, 53) == (date(2022,1,3), date(2022,1,9))  ← 2021 只有 52 週，
   此呼叫必須 raise ValueError，不可回傳錯誤日期
4. 不得 import 標準函式庫以外的套件"""

TESTS = '''
from datetime import date
assert iso_week_range(2026, 1) == (date(2025,12,29), date(2026,1,4)), "week1"
assert iso_week_range(2026, 36) == (date(2026,8,31), date(2026,9,6)), "week36"
try:
    iso_week_range(2021, 53); raise AssertionError("2021 沒有第 53 週，應該要 raise ValueError")
except ValueError:
    pass
print("ALL PASS")
'''

def check(text):
    mm = re.search(r"```(?:python)?\n(.*?)```", text, re.S)
    if not mm:
        return False, "回覆中找不到 ```python 程式碼區塊。"
    code = mm.group(1)
    if re.search(r"^\s*import\s+(?!datetime|calendar|typing)(\w+)", code, re.M):
        return False, "使用了標準函式庫以外的套件。"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code + "\n" + TESTS); path = f.name
    r = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=60)
    if r.returncode == 0 and "ALL PASS" in r.stdout:
        pathlib.Path("/Users/Shared/antigravity-bridge/bench/accepted.py").write_text(code)
        return True, "全部測試通過。"
    err = (r.stderr.strip().splitlines() or ["(無錯誤輸出)"])[-1]
    return False, f"執行測試失敗：{err}"

print("主管模式：派工 → 實際執行測試 → 不過就退回")
res = m.supervise(TASK, CRITERIA, check, model="gemini-3.7-flash-high", max_rounds=3)
print(f"\n結果：{'驗收通過' if res['ok'] else '三回合內未通過'}，共 {len(res['rounds'])} 回合")
