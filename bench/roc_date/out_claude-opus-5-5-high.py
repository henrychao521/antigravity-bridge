import re
from datetime import date

_FULLWIDTH = {0xFF10 + i: ord("0") + i for i in range(10)}
_FULLWIDTH.update({0xFF0F: ord("/"), 0xFF0E: ord("."), 0xFF0D: ord("-")})

_CN_DIGITS = {
    "〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}

_SEP_RE = re.compile(r"([0-9]+)([/.\-])([0-9]+)\2([0-9]+)")
_YMD_RE = re.compile(r"(?:民國)?([^年月日]+)年([^年月日]+)月([^年月日]+)日")
_ASCII_NUM_RE = re.compile(r"[0-9]+")


def _single_nonzero(c: str) -> int | None:
    if len(c) == 1 and c in _CN_DIGITS and _CN_DIGITS[c] != 0:
        return _CN_DIGITS[c]
    return None


def _parse_cn(s: str) -> int | None:
    if not s:
        return None
    # 逐位寫法：一一五、〇五
    if all(c in _CN_DIGITS for c in s):
        return int("".join(str(_CN_DIGITS[c]) for c in s))
    if any(c not in _CN_DIGITS and c not in "十百" for c in s):
        return None

    total = 0
    rest = s
    if "百" in rest:
        h, _, rest = rest.partition("百")
        hv = _single_nonzero(h)
        if hv is None or "百" in rest:
            return None
        total = hv * 100
        if rest == "":
            return total
        if rest[0] in "〇零":
            uv = _single_nonzero(rest[1:])
            if uv is None:
                return None
            return total + uv

    if "十" in rest:
        t, _, u = rest.partition("十")
        if "十" in u:
            return None
        if t == "":
            tens = 1
        else:
            tv = _single_nonzero(t)
            if tv is None:
                return None
            tens = tv
        if u == "":
            units = 0
        else:
            uv = _single_nonzero(u)
            if uv is None:
                return None
            units = uv
        return total + tens * 10 + units

    return None


def _parse_part(p: str, allow_yuan: bool = False) -> int | None:
    if _ASCII_NUM_RE.fullmatch(p):
        return int(p)
    if allow_yuan and p == "元":
        return 1
    return _parse_cn(p)


def _build(y: int | None, m: int | None, d: int | None) -> str | None:
    if y is None or m is None or d is None:
        return None
    if y < 1:
        return None
    ad_year = y + 1911
    if ad_year > 9999:
        return None
    try:
        return date(ad_year, m, d).isoformat()
    except (ValueError, OverflowError):
        return None


def roc_to_iso(s: str) -> str | None:
    try:
        if not isinstance(s, str):
            return None
        t = s.translate(_FULLWIDTH).strip()
        if not t:
            return None

        m = _SEP_RE.fullmatch(t)
        if m:
            return _build(int(m.group(1)), int(m.group(3)), int(m.group(4)))

        m = _YMD_RE.fullmatch(t)
        if m:
            y = _parse_part(m.group(1), allow_yuan=True)
            mo = _parse_part(m.group(2))
            d = _parse_part(m.group(3))
            return _build(y, mo, d)

        return None
    except Exception:
        return None
