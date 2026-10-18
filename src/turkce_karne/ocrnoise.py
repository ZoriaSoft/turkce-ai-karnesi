"""Seeded OCR-noise injection for synthetic extraction tasks.

``render_document`` fills a template's ``{field}`` placeholders with
equivalence-preserving display variants (Turkish-aware case drift,
TR/EN number formatting, alternate date formats) and injects realistic
OCR noise into every *other* character region: diacritic stripping,
common character misreads (O/0, l/1, S/5), stray spaces, punctuation
jitter, indents and separator artifacts.

Expected values therefore stay canonical — the model must still recover
them — while the surrounding document looks like a real bad scan.
Everything derives from one ``random.Random`` seed, so the emitted
dataset is reproducible byte-for-byte.
"""

from __future__ import annotations

import random
import re
from typing import Any

from .textnorm import tr_lower, tr_upper

_FIELD_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")

# diacritic strip — the single most common OCR artifact on Turkish text
_FOLD = str.maketrans(
    {
        "ç": "c", "Ç": "C",
        "ğ": "g", "Ğ": "G",
        "ı": "i", "I": "I", "İ": "I",
        "ö": "o", "Ö": "O",
        "ş": "s", "Ş": "S",
        "ü": "u", "Ü": "U",
    }
)

# plausible glyph misreads (both directions are fine — targets only)
_LETTER_SWAP = {
    "o": "0", "O": "0",
    "l": "1", "I": "1",
    "S": "5", "s": "5",
    "B": "8",
    "G": "6",
}
_DIGIT_SWAP = {"0": "O", "1": "l", "5": "S", "8": "B", "6": "G"}

_MONTHS_TR = [
    "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]
_MONTHS_ASCII = [
    "", "Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran",
    "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik",
]


def _ascii_fold(s: str) -> str:
    return s.translate(_FOLD)


def field_variant(value: Any, kind: str, rng: random.Random) -> str:
    """One displayed form of a canonical value that ``_values_equal``
    still accepts: case drift via Turkish-aware case functions, TR/EN
    numeric formatting, and alternate date spellings. ``code`` and
    ``plate`` kinds are shown verbatim (no equivalent-safe drift)."""
    if kind == "date":
        y, m, d = str(value).split("-")
        mons = _MONTHS_TR if rng.random() < 0.5 else _MONTHS_ASCII
        return rng.choice(
            [
                f"{int(d)}.{int(m)}.{y}",
                f"{d}.{m}.{y}",
                f"{d}/{m}/{y}",
                f"{d}-{m}-{y}",
                f"{int(d)} {mons[int(m)]} {y}",
            ]
        )
    if kind in ("money", "num"):
        v = float(value)
        cents = round((v - int(v)) * 100)
        tr = f"{int(v):,}".replace(",", ".") + f",{cents:02d}"
        en = f"{int(v):,}" + f".{cents:02d}"
        if kind == "money":
            return rng.choice([tr, tr + " TL", "₺" + tr, en])
        return rng.choice([tr, en])
    if kind == "int":
        v = int(value)
        return rng.choice([str(v), f"{v:02d}"])
    if kind in ("name", "text"):
        return rng.choice([str(value), tr_upper(str(value)),
                           tr_lower(str(value))])
    # code, plate: shown exactly
    return str(value)


def _noisify_segment(s: str, rng: random.Random, level: float) -> str:
    """Character-level noise on a non-field text region."""
    if not s:
        return s
    # occasional case drift of a whole label-ish segment
    if (
        level
        and rng.random() < 0.08 * level
        and sum(c.isalpha() for c in s) >= 3
        and not s.isupper()
    ):
        s = tr_upper(s)
    out: list[str] = []
    for ch in s:
        if ch.isalpha():
            r = rng.random()
            if r < 0.055 * level:
                out.append(_ascii_fold(ch))
            elif r < (0.055 + 0.018) * level:
                out.append(_LETTER_SWAP.get(ch, ch))
            else:
                out.append(ch)
        elif ch.isdigit():
            if rng.random() < 0.012 * level:
                out.append(_DIGIT_SWAP.get(ch, ch))
            else:
                out.append(ch)
        elif ch == " ":
            if rng.random() < 0.012 * level:
                continue  # dropped space
            out.append(ch)
        elif ch == ":" and rng.random() < 0.15 * level:
            out.append(" :")
        elif ch in "-–—" and rng.random() < 0.10 * level:
            out.append(" ")
        else:
            out.append(ch)
        # stray space injected mid-word
        if ch.isalpha() and rng.random() < 0.006 * level:
            out.append(" ")
    return "".join(out)


def render_document(
    fields: dict[str, tuple[str, Any]],
    lines: list[str],
    *,
    seed: int,
    level: float = 1.0,
) -> tuple[str, dict[str, Any]]:
    """Render a noised document and its canonical expected map.

    ``fields`` maps ``{name}`` placeholders to ``(kind, canonical)`` —
    kind is one of ``date|money|num|int|name|text|code|plate``. Every
    placeholder in ``lines`` must exist in ``fields``. Returns
    ``(input_text, expected)`` where ``expected`` keeps the canonical
    values unchanged.
    """
    rng = random.Random(seed)
    display = {
        name: field_variant(canon, kind, rng)
        for name, (kind, canon) in fields.items()
    }
    out_lines: list[str] = []
    for tpl in lines:
        if not tpl.strip():
            out_lines.append("")
            continue
        parts = _FIELD_RE.split(tpl)  # even = text, odd = field name
        buf: list[str] = []
        for i, part in enumerate(parts):
            if i % 2 == 0:
                buf.append(_noisify_segment(part, rng, level))
            else:
                if part not in display:
                    raise ValueError(
                        f"template references unknown field {part!r}"
                    )
                buf.append(display[part])
        line = "".join(buf)
        if line.strip() and rng.random() < 0.08 * level:
            line = " " * rng.randint(1, 3) + line
        out_lines.append(line)
        r = rng.random()
        if r < 0.05 * level:
            out_lines.append("-" * rng.randint(8, 40))
        elif r < 0.10 * level:
            out_lines.append("")
    expected = {name: canon for name, (_, canon) in fields.items()}
    return "\n".join(out_lines).strip("\n") + "\n", expected
