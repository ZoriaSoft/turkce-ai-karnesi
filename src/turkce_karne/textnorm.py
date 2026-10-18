"""Text normalization helpers.

All comparisons go through Turkish-aware normalization: dotted/dotless I is
folded deterministically (I->ı, İ->i), whitespace is collapsed, and the
dotless ı is preserved as a distinct character.
"""

from __future__ import annotations

import re
import unicodedata

_PUNCT_RE = re.compile(r"[^\w\sçğıiöüâîû€₺]", re.UNICODE)
_WORD_RE = re.compile(r"[\wçğıiöüâîû€₺']+", re.UNICODE)
_WS_RE = re.compile(r"\s+")
_SENT_RE = re.compile(r"[.!?…]+(?:\s|$)")

# Dotted I in lowercase (U+0130) folds to plain i. Uppercase I folds to
# dotless ı, matching real Turkish orthography.
_LOWER_MAP = str.maketrans({"I": "ı", "İ": "i"})


def tr_lower(s: str) -> str:
    return s.translate(_LOWER_MAP).lower()


_UPPER_MAP = str.maketrans({"i": "İ", "ı": "I"})


def tr_upper(s: str) -> str:
    return s.translate(_UPPER_MAP).upper()


def flatten_ws(s: str) -> str:
    return _WS_RE.sub(" ", s).strip()


def norm_text(s: str, *, keep_punct: bool = False) -> str:
    """Lowercase Turkish-aware, collapse whitespace, optionally strip punctuation."""
    s = unicodedata.normalize("NFC", s)
    s = tr_lower(s)
    s = flatten_ws(s)
    if not keep_punct:
        s = _PUNCT_RE.sub(" ", s)
        s = flatten_ws(s)
    return s


def words(s: str) -> list[str]:
    return _WORD_RE.findall(s)


def word_count(s: str) -> int:
    return len(words(s))


def sentence_count(s: str) -> int:
    stripped = s.strip()
    if not stripped:
        return 0
    n = len(_SENT_RE.findall(stripped))
    # trailing text without terminal punctuation still counts as a sentence
    if not _SENT_RE.search(stripped[-2:] + " "):
        n += 1
    return max(n, 1)


def line_count(s: str) -> int:
    return sum(1 for ln in s.splitlines() if ln.strip())


# Turkish-specific characters (ASCII 'i' deliberately excluded — it appears
# everywhere in English; dotless 'ı' is the Turkish giveaway)
TR_CHARS = set("çğşıöüâîû")


def has_turkish_char(w: str) -> bool:
    return any(c in TR_CHARS for c in w)


def to_number(s: object) -> float | None:
    """Parse int/float or Turkish-ish number strings.

    Handles: ``12,5`` decimal comma, ``1.234,56`` TR formatting,
    ``1,234.56`` EN formatting, ``%8``, ``1e3``.
    """
    if isinstance(s, bool):
        return None
    if isinstance(s, (int, float)):
        return float(s)
    if not isinstance(s, str):
        return None
    t = s.strip()
    if not t:
        return None
    t = t.replace("%", "").replace("TL", "").replace("₺", "").strip()
    # normalize separators: keep the rightmost of ,/. as decimal mark
    last_comma, last_dot = t.rfind(","), t.rfind(".")
    if last_comma > last_dot:
        # comma is decimal: 1.234,56 -> 1234.56 ; 12,5 -> 12.5
        t = t.replace(".", "").replace(",", ".")
    elif last_dot > last_comma:
        t = t.replace(",", "")
    else:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


_TR_MONTHS = {
    "ocak": 1, "subat": 2, "şubat": 2, "mart": 3, "nisan": 4, "mayis": 5,
    "mayıs": 5, "haziran": 6, "temmuz": 7, "agustos": 8, "ağustos": 8,
    "eylul": 9, "eylül": 9, "ekim": 10, "kasim": 11, "kasım": 11,
    "aralik": 12, "aralık": 12,
}

_DATE_PATTERNS = [
    re.compile(r"(?P<y>\d{4})[-/.](?P<m>\d{1,2})[-/.](?P<d>\d{1,2})"),
    re.compile(r"(?P<d>\d{1,2})[-/.](?P<m>\d{1,2})[-/.](?P<y>\d{4})"),
    re.compile(
        r"(?P<d>\d{1,2})\s+(?P<mon>[A-Za-zçğıiöüÇĞİÖÜâîû]+)\s+(?P<y>\d{4})"
    ),
]


def to_date_iso(s: object) -> str | None:
    """Normalize date-ish values to ``YYYY-MM-DD`` when recognizable."""
    if not isinstance(s, str):
        return None
    t = s.strip()
    for pat in _DATE_PATTERNS:
        m = pat.search(t)
        if not m:
            continue
        g = m.groupdict()
        try:
            y = int(g["y"])
            d = int(g["d"])
            if "mon" in g and g.get("mon"):
                mon = _TR_MONTHS.get(norm_text(g["mon"]))
                if mon is None:
                    continue
                m_i = mon
            else:
                m_i = int(g["m"])
            if not (1 <= m_i <= 12 and 1 <= d <= 31):
                continue
            return f"{y:04d}-{m_i:02d}-{d:02d}"
        except (ValueError, KeyError):
            continue
    return None
