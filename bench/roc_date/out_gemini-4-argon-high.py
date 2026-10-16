from datetime import date
import re

_DIGITS_RE = re.compile(r"^[0-9０-９]+$")
_SEP_RE = re.compile(
    r"^(?P<y>[0-9０-９]+)(?P<sep>[/.\-／．－])(?P<m>[0-9０-９]+)(?P=sep)(?P<d>[0-9０-９]+)$"
)
_YMD_RE = re.compile(r"^(?:民國)?(?P<y>.+)年(?P<m>.+)月(?P<d>.+)日$")

_CN_DIGITS = {
    "〇": 0,
    "零": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}

_CN_TENS_RE = re.compile(
    r"^(?P<t>[一二三四五六七八九])?十(?P<u>[一二三四五六七八九])?$"
)
_CN_HUNDREDS_EXACT_RE = re.compile(r"^(?P<h>[一二三四五六七八九])百$")
_CN_HUNDREDS_ZERO_RE = re.compile(
    r"^(?P<h>[一二三四五六七八九])百[〇零](?P<u>[一二三四五六七八九])$"
)
_CN_HUNDREDS_TENS_RE = re.compile(
    r"^(?P<h>[一二三四五六七八九])百(?P<t>[一二三四五六七八九])?十(?P<u>[一二三四五六七八九])?$"
)


def _parse_cn_number(text: str, allow_yuan: bool = False) -> int | None:
    if allow_yuan and text == "元":
        return 1
    if not text:
        return None
    if all(ch in _CN_DIGITS for ch in text):
        val = 0
        for ch in text:
            val = val * 10 + _CN_DIGITS[ch]
        return val
    if m := _CN_TENS_RE.fullmatch(text):
        t = _CN_DIGITS[m.group("t")] if m.group("t") else 1
        u = _CN_DIGITS[m.group("u")] if m.group("u") else 0
        return t * 10 + u
    if m := _CN_HUNDREDS_EXACT_RE.fullmatch(text):
        return _CN_DIGITS[m.group("h")] * 100
    if m := _CN_HUNDREDS_ZERO_RE.fullmatch(text):
        return _CN_DIGITS[m.group("h")] * 100 + _CN_DIGITS[m.group("u")]
    if m := _CN_HUNDREDS_TENS_RE.fullmatch(text):
        h = _CN_DIGITS[m.group("h")]
        t = _CN_DIGITS[m.group("t")] if m.group("t") else 1
        u = _CN_DIGITS[m.group("u")] if m.group("u") else 0
        return h * 100 + t * 10 + u
    return None


def _parse_ymd_part(text: str, allow_yuan: bool = False) -> int | None:
    if _DIGITS_RE.fullmatch(text):
        return int(text)
    return _parse_cn_number(text, allow_yuan=allow_yuan)


def roc_to_iso(s: str) -> str | None:
    try:
        if not isinstance(s, str):
            return None
        s = s.strip()
        if not s or s.startswith("民國前"):
            return None

        if m := _SEP_RE.fullmatch(s):
            roc_year = int(m.group("y"))
            month = int(m.group("m"))
            day = int(m.group("d"))
        elif m := _YMD_RE.fullmatch(s):
            roc_year = _parse_ymd_part(m.group("y"), allow_yuan=True)
            month = _parse_ymd_part(m.group("m"), allow_yuan=False)
            day = _parse_ymd_part(m.group("d"), allow_yuan=False)
            if roc_year is None or month is None or day is None:
                return None
        else:
            return None

        if roc_year <= 0:
            return None

        return date(roc_year + 1911, month, day).isoformat()
    except Exception:
        return None
