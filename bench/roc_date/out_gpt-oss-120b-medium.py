import datetime
import re
from typing import Optional

# full‑width to half‑width conversion tables
_FULLWIDTH_DIGITS = {chr(0xFF10 + i): str(i) for i in range(10)}
_FULLWIDTH_PUNCT = {
    "／": "/",
    "．": ".",
    "－": "-",
    "　": " ",  # full‑width space
}

# Chinese numerals
_CH_NUM_MAP = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "百": 100,
    "千": 1000,
    "元": 1,
}

def _normalize(s: str) -> str:
    """Replace full‑width digits/punctuations with ASCII equivalents and strip."""
    s = s.strip()
    # full‑width digits
    for fw, hw in _FULLWIDTH_DIGITS.items():
        s = s.replace(fw, hw)
    # full‑width punctuation
    for fw, hw in _FULLWIDTH_PUNCT.items():
        s = s.replace(fw, hw)
    return s

def _chinese_to_int(text: str) -> Optional[int]:
    """Convert a simple Chinese numeral (supports 零、〇、一‑九、十、百、千、元) to int."""
    if not text:
        return None
    # handle the special case "元"
    if text == "元":
        return 1

    total = 0
    unit = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch not in _CH_NUM_MAP:
            return None
        val = _CH_NUM_MAP[ch]

        # unit characters (十、百、千) multiply the preceding digit (if any)
        if ch in ("十", "百", "千"):
            if unit == 0:
                # e.g. 十 => 10, 百 => 100
                unit = 1
            unit *= val
            total += unit
            unit = 0
        else:
            # digit character
            unit = val
            # look ahead: if next char is a unit, the multiplication will happen in next loop
            # else we add now (for last digit)
            if i + 1 == len(text) or text[i + 1] not in ("十", "百", "千"):
                total += unit
                unit = 0
        i += 1
    return total

def _parse_part(part: str) -> Optional[int]:
    """Parse a numeric part which may be Arabic digits or Chinese numerals."""
    if part.isdigit():
        return int(part)
    return _chinese_to_int(part)

def roc_to_iso(s: str) -> Optional[str]:
    """
    Convert a Taiwanese ROC date string to ISO format (YYYY‑MM‑DD).
    Returns ``None`` for invalid or unparsable inputs.
    """
    if not s:
        return None

    s = _normalize(s)

    # Reject strings starting with "民國前"
    if s.startswith("民國前"):
        return None

    # 1️⃣ Delimiter style: 115/10/14 or 115.10.14 or 115-10-14
    m = re.fullmatch(r"(?P<year>\d{1,4})(?P<sep>[/\.-])(?P<month>\d{1,2})(?P=sep)(?P<day>\d{1,2})", s)
    if m:
        year = int(m.group("year"))
        month = int(m.group("month"))
        day = int(m.group("day"))
        if year <= 0:
            return None
        g_year = year + 1911
        try:
            datetime.date(g_year, month, day)
        except ValueError:
            return None
        return f"{g_year:04d}-{month:02d}-{day:02d}"

    # 2️⃣ Chinese style with 年月日 (optional leading "民國")
    # Allow Arabic digits after normalization as well.
    pattern = (
        r"^(?:民國)?"
        r"(?P<y>[\d一二三四五六七八九零〇十百千元]+)年"
        r"(?P<m>[\d一二三四五六七八九零〇十]+)月"
        r"(?P<d>[\d一二三四五六七八九零〇十]+)日$"
    )
    m = re.fullmatch(pattern, s)
    if m:
        y_part, m_part, d_part = m.group("y"), m.group("m"), m.group("d")
        year = _parse_part(y_part)
        month = _parse_part(m_part)
        day = _parse_part(d_part)
        if None in (year, month, day):
            return None
        if year <= 0:
            return None
        g_year = year + 1911
        try:
            datetime.date(g_year, month, day)
        except ValueError:
            return None
        return f"{g_year:04d}-{month:02d}-{day:02d}"

    # If none of the patterns matched, return None
    return None
