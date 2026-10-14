import re, datetime
_FW = str.maketrans("０１２３４５６７８９／．－", "0123456789/.-")
_D = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
def _cn(t):
    if t.isdigit(): return int(t)
    if t == "元": return 1
    if not t or any(c not in _D and c not in "十百" for c in t): return None
    if "十" not in t and "百" not in t:
        return int("".join(str(_D[c]) for c in t))
    n, cur = 0, 0
    for c in t:
        if c in _D: cur = _D[c]
        elif c == "百": n += (cur or 1) * 100; cur = 0
        elif c == "十": n += (cur or 1) * 10; cur = 0
    return n + cur
def roc_to_iso(s):
    try:
        s = s.strip().translate(_FW)
        if s.startswith("民國前"): return None
        s = s.removeprefix("民國")
        m = re.fullmatch(r"(\d+)([/.-])(\d+)\2(\d+)", s)
        if m: y, mo, d = int(m[1]), int(m[3]), int(m[4])
        else:
            m = re.fullmatch(r"([0-9〇零一二三四五六七八九十百元]+)年([0-9〇零一二三四五六七八九十]+)月([0-9〇零一二三四五六七八九十]+)日", s)
            if not m: return None
            y, mo, d = _cn(m[1]), _cn(m[2]), _cn(m[3])
            if None in (y, mo, d): return None
        if y < 1: return None
        return datetime.date(y + 1911, mo, d).isoformat()
    except Exception:
        return None
