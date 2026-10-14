import re
from datetime import date

_FULLWIDTH_TABLE = str.maketrans({
    "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
    "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
    "／": "/", "．": ".", "－": "-",
})

_CN_DIGITS = {
    "〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}

_TOKEN = r"[0-9〇零一二三四五六七八九十百元]+"

_YMD_RE = re.compile(rf"(?:民國)?({_TOKEN})年({_TOKEN})月({_TOKEN})日")
_SEP_RE = re.compile(r"([0-9]+)([/.\-])([0-9]+)\2([0-9]+)")
_ARABIC_RE = re.compile(r"[0-9]+")


def _cn_to_int(t: str, allow_yuan: bool = False) -> int | None:
    """Parse a Chinese numeral string (positional or counting style)."""
    if t == "元":
        return 1 if allow_yuan else None
    if "元" in t:
        return None

    # Positional style, e.g. 一一五 / 〇五
    if "百" not in t and "十" not in t:
        if not all(c in _CN_DIGITS for c in t):
            return None
        return int("".join(str(_CN_DIGITS[c]) for c in t))

    # Counting style, e.g. 一百一十五 / 二十 / 十四
    total = 0
    rest = t
    if "百" in rest:
        head, rest = rest.split("百", 1)
        if len(head) != 1 or _CN_DIGITS.get(head, 0) <= 0:
            return None
        total += _CN_DIGITS[head] * 100

    if "十" in rest:
        head, tail = rest.split("十", 1)
        if head == "":
            tens = 1
        elif len(head) == 1 and _CN_DIGITS.get(head, 0) > 0:
            tens = _CN_DIGITS[head]
        else:
            return None
        if tail == "":
            ones = 0
        elif len(tail) == 1 and _CN_DIGITS.get(tail, 0) > 0:
            ones = _CN_DIGITS[tail]
        else:
            return None
        total += tens * 10 + ones
    elif rest != "":
        # Only valid after 百, e.g. 一百〇五
        r = rest.lstrip("〇零")
        if len(r) == 1 and len(r) != len(rest) and _CN_DIGITS.get(r, 0) > 0:
            total += _CN_DIGITS[r]
        else:
            return None
    return total


def _token_to_int(t: str, allow_yuan: bool = False) -> int | None:
    if _ARABIC_RE.fullmatch(t):
        return int(t)
    return _cn_to_int(t, allow_yuan)


def roc_to_iso(s: str) -> str | None:
    try:
        if not isinstance(s, str):
            return None
        text = s.strip().translate(_FULLWIDTH_TABLE)
        if not text:
            return None

        m = _SEP_RE.fullmatch(text)
        if m:
            y_tok, _, m_tok, d_tok = m.groups()
        else:
            m = _YMD_RE.fullmatch(text)
            if not m:
                return None
            y_tok, m_tok, d_tok = m.groups()

        year = _token_to_int(y_tok, allow_yuan=True)
        month = _token_to_int(m_tok)
        day = _token_to_int(d_tok)
        if year is None or month is None or day is None:
            return None
        if year < 1:
            return None

        return date(year + 1911, month, day).isoformat()
    except Exception:
        return None
