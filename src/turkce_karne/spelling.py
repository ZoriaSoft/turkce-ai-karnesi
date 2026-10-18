"""Deterministic Turkish orthography scanners used by ``spelling_rules``.

Every rule here is high-precision by design: it only fires on cases that
are unambiguous errors under TDK conventions, so a clean response never
loses points to a heuristic false positive. Turkish morphology is *not*
modeled — the attached suffix side of de/da (locative vs clitic) is
deliberately out of scope; the separated clitic's vowel harmony is not.

Each scanner takes the raw response plus an ``allow`` set of extra stems
the task author wants to exclude, and returns short human-readable
violation strings.
"""

from __future__ import annotations

import re

from .textnorm import norm_text
from .turkish_lexicon import TURKISH_WORDS

# token: Turkish letters/digits/apostrophe; ASCII letters kept so foreign
# words can be filtered out by the stem blocklist
_TOK_RE = re.compile(r"[0-9A-Za-zÇĞİIıÖŞÜçğıöşüâîû']+")

# word boundary helpers: (?<![\w']) anchors are not usable on the left of
# an alternation, so every pattern uses explicit lookarounds
_WB_L = r"(?<![\w'])"
_WB_R = r"(?![\w'])"

# ---------------------------------------------------------------------------
# rule 1: question particle written as a suffix
#
# "mi/mı/mu/mü" (and personal forms) is always a separate word.
# Bare \w+mi would false-positive on legit accusative/possessive endings
# ("arabamı", "ismi"), so only the personal forms are flagged: no Turkish
# suffix ends in -musun/-misin/-miyim/-miyiz/-miyiz. The "-miş"
# evidential suffix is excluded by requiring the token to END at the
# particle ("gelmişmi" still flags).
_MI_ATTACHED = re.compile(
    _WB_L
    + r"[\w']*[^\W\d_' ](?:musun|misin|mısın|müsün|miyim|mıyım|muyum|müyüm|"
    r"miyiz|mıyız|muyuz|müyüz|miyiz|misiniz|mısınız|musunuz|müsünüz)"
    + _WB_R
    + r"|"
    + _WB_L
    + r"[\w']+?(?:miş|mış|muş|müş)(?:mi|mı|mu|mü)"
    + _WB_R
)


def scan_mi_attached(text: str, allow: set[str] | None = None) -> list[str]:
    out = []
    for m in _MI_ATTACHED.finditer(text):
        tok = m.group(0)
        if allow and norm_text(tok) in allow:
            continue
        out.append(f"question particle attached: '{tok}'")
    return out


# ---------------------------------------------------------------------------
# rule 2: question particle vowel harmony
#
# The particle must agree with the LAST vowel of the preceding word:
#   a/ı -> mı,  o/u -> mu,  e/i -> mi,  ö/ü -> mü.
# Applied to the separate-word form only. False-positive guards: the stem
# must look Turkish (lexicon hit, Turkish-specific char, or an inflected
# shape) — a small blocklist covers English borrowings and solfège notes.
_VOWEL_PARTICLE = {
    "a": "mı",
    "ı": "mı",
    "o": "mu",
    "u": "mu",
    "e": "mi",
    "i": "mi",
    "ö": "mü",
    "ü": "mü",
}
_VOWELS = set(_VOWEL_PARTICLE)
_PARTICLES = set(_VOWEL_PARTICLE.values())

# stems where the rule does not apply: solfège notes (nota mi), frequent
# English words, units, and anything else authors hit as a false positive
_MI_STEM_SKIP = {
    # solfège / music
    "do", "re", "mi", "fa", "sol", "la", "si", "nota", "notası",
    "ton", "gam",
    # common foreign words seen in Turkish text (harmony often wrong-looking)
    "email", "mail", "e-mail", "the", "a", "i", "to", "in", "on", "at",
    "ok", "no", "wifi", "bio", "auto", "kilo", "zero", "metro",
    "video", "foto", "pro", "demo", "info", "logo", "euro", "duo",
    "piano", "cello", "alto", "soprano", "tempo",
    # acronyms/short tokens that end sentences
    "pc", "tv", "ai", "it", "ui", "id", "ip", "vs", "km", "cm", "mm",
}


def _stem_looks_turkish(stem: str) -> bool:
    """Decide whether harmony applies to this stem."""
    if not stem or stem in _MI_STEM_SKIP:
        return False
    if stem in TURKISH_WORDS:
        return True
    if any(c in stem for c in "çğıöşüâîû"):
        return True
    # pure-ASCII: accept stems ≥3 chars whose vowels are common Turkish
    # endings; reject obvious Latin/English stems (contain 'w', 'x', 'q',
    # 'j' or the consonant clusters Turkish doesn't have at word end)
    if re.search(r"[qwxj]", stem):
        return False
    return len(stem) >= 3


def scan_mi_harmony(text: str, allow: set[str] | None = None) -> list[str]:
    out = []
    toks = _TOK_RE.findall(text)
    prev: str | None = None
    for tok in toks:
        tl = norm_text(tok)
        if tl in _PARTICLES and prev is not None:
            stem = norm_text(prev.rstrip("'"))
            if allow and stem in allow:
                prev = None
                continue
            if _stem_looks_turkish(stem):
                vowels = [c for c in stem if c in _VOWELS]
                if vowels:
                    want = _VOWEL_PARTICLE[vowels[-1]]
                    if want != tl:
                        out.append(
                            f"question particle harmony: '{prev} {tok}' "
                            f"should be '{want}'"
                        )
            prev = None
            continue
        prev = tok
    return out


# ---------------------------------------------------------------------------
# rule 3: "ki" left separate where TDK requires the joined form
#
# After locative/ablative endings and most time adverbs the suffix "-ki"
# attaches: bugünkü, evdeki, sendeki, oradaki, bendeki... The separate
# spelling "evde ki" is only legal in the rare "…de/da ki" clause sense
# ("orada ki gördüm" is never standard). A small stop set keeps genuine
# clause-final words (neden, birden, hemen, şimdi+den...) from flagging.
_KI_AFTER = re.compile(
    _WB_L
    + r"([\w']+?(?:de|da|te|ta|den|dan|ten|tan|nde|nda|nden|ndan))\s+ki\b"
    + r"|"
    + _WB_L
    + r"(bugün|dün|yarın|akşam|sabah|öğle|öğlen|gece|şimdi|önce|sonra)"
    r"\s+ki\b",
    re.IGNORECASE,
)
# stems ending in -den/-dan/-ten/-tan that are NOT ablative case forms —
# "neden ki" (as if), "birden ki" never occur joined, but these words are
# monomorphemic so the regex can't tell; keep the explicit list short.
_KI_STOP = {
    "neden", "birden", "hemen", "şimdi", "sonradan", "yukarıdan",
    "aşağıdan", "içeriden", "dışarıdan", "öteden", "beriden",
}

def scan_ki_separate(text: str, allow: set[str] | None = None) -> list[str]:
    out = []
    for m in _KI_AFTER.finditer(text):
        stem_txt = m.group(1) or m.group(2)
        stem = norm_text(stem_txt)
        if m.group(1) is not None and stem in _KI_STOP:
            continue
        if allow and stem in allow:
            continue
        out.append(
            f"'ki' should attach: '{stem_txt} ki' -> '{stem_txt}ki'"
        )
    return out





# ---------------------------------------------------------------------------
# rule 4: fused/misspelled compounds — TDK's canonical error list.
# Every entry is unambiguously wrong as a standalone token. Two classes:
#   strict   — word-boundary only (particles where a suffix tail would
#              hit real words: "demir" contains "demi")
#   inflect  — tolerate an inflectional tail ("herşeyi", "yanlızı")
_TRAPS_STRICT = {
    "yada": "ya da",
    "dahada": "daha da",
    "belkide": "belki de",
    "çunku": "çünkü",
    "çunkü": "çünkü",
    "çünki": "çünkü",
    "mademki": "madem",
    "oysaki": "oysa",
    "demi": "de mi",
    "damı": "da mı",
    "dami": "da mi",
    "demü": "de mü",
    "tşk": "teşekkür",
    "tmm": "tamam",
}
_TRAPS_INFLECT = {
    "birşey": "bir şey",
    "herşey": "her şey",
    "hiçbirşey": "hiçbir şey",
    "birarada": "bir arada",
    "yanlız": "yalnız",
    "yalnış": "yanlış",
    "herkez": "herkes",
}
_TRAP_MAP: dict[str, str] = {**_TRAPS_STRICT, **_TRAPS_INFLECT}
_TRAP_RE = re.compile(
    _WB_L
    + "("
    + "|".join(sorted(_TRAPS_STRICT, key=len, reverse=True))
    + ")"
    + _WB_R
    + "|"
    + _WB_L
    + "("
    + "|".join(sorted(_TRAPS_INFLECT, key=len, reverse=True))
    + r")[\w']*"
    + _WB_R,
    re.IGNORECASE,
)


def scan_compound_traps(text: str, allow: set[str] | None = None) -> list[str]:
    out = []
    for m in _TRAP_RE.finditer(text):
        base = m.group(1) or m.group(2)
        bad = norm_text(base)
        if allow and bad in allow:
            continue
        out.append(
            f"spelling: '{m.group(0)}' should be '{_TRAP_MAP[bad]}'"
        )
    return out




# ---------------------------------------------------------------------------
# rule 5: separated "de/da" clitic vowel harmony
#
# The clitic "de/da" (also/too) is always a separate word, but its vowel
# still harmonizes with the LAST vowel of the preceding word:
#   e/i/ö/ü -> de,   a/ı/o/u -> da
# ("ben de", "okul da"). Front->back has no exceptions: "ben da" is always
# wrong. Back->front has one lexical exception class — Arabic/Persian loan
# stems whose written back vowel takes a front-vowel suffix anyway (fetha
# "saat de", palatal final-l "normal de"); those stems are skipped via
# _DEDA_FRONT_LOANS, and stems containing â/î/û are skipped outright
# (their harmony is lexical: "kâr da" but "kâğıt de"). Attached "de/da"
# stays out of scope — there it may be a legal locative suffix, which
# needs morphology to disambiguate.
_DEDA_PARTICLE = {"de", "da"}
_DEDA_FRONT_VOWELS = set("eiöü")
_DEDA_VOWELS = _DEDA_FRONT_VOWELS | set("aıou")

# stems where "X de" is a legal foreign fixed phrase, not the clitic:
# "Rio de Janeiro", "Tour de France", "nom de plume", "coup de grâce",
# "pas de deux", "point de vue", "fin de semana"... — flagging the
# French/Spanish/Portuguese "de" is always wrong.
_DEDA_STEM_SKIP = {
    "rio", "tour", "nom", "pas", "coup", "fin", "hors", "point", "pot",
    "jeu", "fleur", "cinco", "costa", "boca", "copa", "dia", "sangre",
    "corazon",
}

# back-vowel loan stems that nevertheless take "de" — skipped entirely:
# flagging "saat de" is worse than missing "saat da".
_DEDA_FRONT_LOANS = {
    # fetha: written short a, front realisation (TDK exception list)
    "saat", "sanat", "hakikat", "hikayet", "hidayet", "itaat", "şeriat",
    "zikat", "kudret", "hükümet", "hürmet", "haysiyet", "kanaat",
    "nihayet", "rağbet", "istikbal", "ihtimal",
    # -harf group: kalp -> kalpte
    "kalp", "harf",
    # palatal final l (written back vowel, front suffix)
    "hayal", "alkol", "kontrol", "normal", "lokal", "global", "sosyal",
    "sanal", "dijital", "final", "metal", "terminal", "ideal", "real",
    "reel", "usul", "meşgul", "kabul", "makbul", "mesul", "resul", "rol",
    "sol", "gol", "moral", "sinyal", "festival", "kristal", "total",
    "viral", "futbol", "hilal", "kemal", "cemal", "vebal", "misal",
    "emsal", "makul", "petrol", "kolesterol", "şevval", "mahal", "hal",
}


def _deda_stem_ok(stem: str) -> bool:
    """Decide whether de/da harmony applies to this stem."""
    if not stem or stem in _DEDA_FRONT_LOANS or stem in _DEDA_STEM_SKIP:
        return False
    # â/î/û stems have lexical harmony (kâr da vs kâğıt de) — skip
    if any(c in stem for c in "âîû"):
        return False
    if stem in TURKISH_WORDS:
        return True
    if any(c in stem for c in "çğıöşü"):
        return True
    # pure-ASCII: reject obvious Latin/foreign stems, accept the rest
    if re.search(r"[qwxj]", stem):
        return False
    return len(stem) >= 3


def scan_de_da_harmony(text: str, allow: set[str] | None = None) -> list[str]:
    out = []
    toks = _TOK_RE.findall(text)
    prev: str | None = None
    for tok in toks:
        tl = norm_text(tok)
        if tl in _DEDA_PARTICLE and prev is not None:
            stem = norm_text(prev.rstrip("'"))
            if allow and stem in allow:
                prev = None
                continue
            if _deda_stem_ok(stem):
                vowels = [c for c in stem if c in _DEDA_VOWELS]
                if vowels:
                    want = (
                        "de" if vowels[-1] in _DEDA_FRONT_VOWELS else "da"
                    )
                    if want != tl:
                        out.append(
                            f"clitic 'de/da' harmony: '{prev} {tok}' "
                            f"should be '{want}'"
                        )
            prev = None
            continue
        prev = tok
    return out


# ---------------------------------------------------------------------------
# registry — used by the ``spelling_rules`` check. Rule names are stable;
# a spec may subset them via ``rules: [...]``.
SCANNERS = {
    "mi_attached": scan_mi_attached,
    "mi_harmony": scan_mi_harmony,
    "ki_separate": scan_ki_separate,
    "compound_traps": scan_compound_traps,
    "de_da_harmony": scan_de_da_harmony,
}
