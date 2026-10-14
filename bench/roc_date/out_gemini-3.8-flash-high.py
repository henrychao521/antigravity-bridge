from datetime import date
import re
import unicodedata


def _parse_chinese_num(s: str) -> int | None:
    if not s:
        return None
    if s == "元":
        return 1

    digits = {
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

    if all(c in digits for c in s):
        val = 0
        for c in s:
            val = val * 10 + digits[c]
        return val

    valid_chars = set(digits.keys()) | {"十", "百"}
    if not all(c in valid_chars for c in s):
        return None

    if "百" in s:
        if s.count("百") > 1:
            return None
        hundred_part, _, rest = s.partition("百")
        if hundred_part == "":
            h_val = 1
        elif len(hundred_part) == 1 and hundred_part in digits and digits[hundred_part] != 0:
            h_val = digits[hundred_part]
        else:
            return None

        total = h_val * 100
        if rest == "":
            return total

        if rest[0] in ("〇", "零"):
            if len(rest) == 2 and rest[1] in digits and digits[rest[1]] != 0:
                return total + digits[rest[1]]
            return None

        if "十" in rest:
            if rest.count("十") > 1:
                return None
            ten_part, _, unit_part = rest.partition("十")
            if ten_part == "":
                t_val = 1
            elif len(ten_part) == 1 and ten_part in digits and digits[ten_part] != 0:
                t_val = digits[ten_part]
            else:
                return None

            if unit_part == "":
                u_val = 0
            elif len(unit_part) == 1 and unit_part in digits and digits[unit_part] != 0:
                u_val = digits[unit_part]
            else:
                return None

            return total + t_val * 10 + u_val
        else:
            return None

    if "十" in s:
        if s.count("十") > 1:
            return None
        ten_part, _, unit_part = s.partition("十")
        if ten_part == "":
            t_val = 1
        elif len(ten_part) == 1 and ten_part in digits and digits[ten_part] != 0:
            t_val = digits[ten_part]
        else:
            return None

        if unit_part == "":
            u_val = 0
        elif len(unit_part) == 1 and unit_part in digits and digits[unit_part] != 0:
            u_val = digits[unit_part]
        else:
            return None

        return t_val * 10 + u_val

    return None


def _parse_token(token: str) -> int | None:
    if not token:
        return None
    if token.isdigit():
        return int(token)
    return _parse_chinese_num(token)


def roc_to_iso(s: str) -> str | None:
    if not isinstance(s, str):
        return None
    try:
        s = unicodedata.normalize("NFKC", s).strip()
        if not s:
            return None
        if s.startswith("民國前"):
            return None

        m_delim = re.fullmatch(r"([0-9]+)([/.-])([0-9]+)\2([0-9]+)", s)
        if m_delim:
            roc_year = int(m_delim.group(1))
            month = int(m_delim.group(3))
            day = int(m_delim.group(4))
        else:
            m_cjk = re.fullmatch(r"(?:民國)?([^年月日\s]+)年([^年月日\s]+)月([^年月日\s]+)日", s)
            if not m_cjk:
                return None

            roc_year = _parse_token(m_cjk.group(1))
            month = _parse_token(m_cjk.group(2))
            day = _parse_token(m_cjk.group(3))

            if roc_year is None or month is None or day is None:
                return None

        if roc_year <= 0:
            return None

        ad_year = roc_year + 1911
        d = date(ad_year, month, day)
        return d.isoformat()
    except Exception:
        return None
