"""Deterministic, reproducible checks.

Each check takes a spec mapping (from the dataset) plus the model response
string and returns a :class:`CheckResult`. Checks never touch the network and
never use randomness — same input, same verdict.

A spec must contain ``type``. Everything else is type-specific. Unknown types
or missing params are dataset bugs and raise :class:`CheckSpecError` at
validation time (see :func:`validate_check_specs`).
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Iterable

from .errors import CheckSpecError
from .model import CheckResult, Task
from .textnorm import (
    has_turkish_char,
    line_count,
    norm_text,
    sentence_count,
    to_date_iso,
    to_number,
    tr_lower,
    word_count,
    words,
)
from .turkish_lexicon import TURKISH_WORDS
from .spelling import SCANNERS


def _need(spec: dict, *names: str) -> None:
    for n in names:
        if n not in spec:
            raise CheckSpecError(f"check {spec.get('type')!r} missing '{n}'")


def _terms(spec: dict) -> list[str]:
    _need(spec, "terms")
    t = spec["terms"]
    if isinstance(t, str):
        t = [t]
    if not isinstance(t, list) or not all(isinstance(x, str) for x in t):
        raise CheckSpecError("'terms' must be a string or list of strings")
    return t


def _mode(spec: dict) -> str:
    mode = spec.get("mode", "literal")
    if mode not in ("literal", "regex"):
        raise CheckSpecError(f"bad mode {mode!r}")
    return mode


def _find(haystack_norm: str, term: str, mode: str) -> bool:
    if mode == "regex":
        return re.search(term, haystack_norm, flags=re.IGNORECASE) is not None
    return norm_text(term) in haystack_norm


# --------------------------------------------------------------------------
# membership / order checks


def _check_contains(spec: dict, resp: str, ctx) -> CheckResult:
    terms = _terms(spec)
    mode = _mode(spec)
    hn = norm_text(resp) if mode == "literal" else resp
    missing = [t for t in terms if not _find(hn, t, mode)]
    return CheckResult(
        type="contains",
        passed=not missing,
        detail={"missing": missing} if missing else {},
    )


def _check_not_contains(spec: dict, resp: str, ctx) -> CheckResult:
    terms = _terms(spec)
    mode = _mode(spec)
    hn = norm_text(resp) if mode == "literal" else resp
    found = [t for t in terms if _find(hn, t, mode)]
    return CheckResult(
        type="not_contains",
        passed=not found,
        detail={"found": found} if found else {},
    )


def _check_word_order(spec: dict, resp: str, ctx) -> CheckResult:
    terms = _terms(spec)
    hn = norm_text(resp)
    pos = 0
    out_of_order: list[str] = []
    for t in terms:
        needle = norm_text(t)
        idx = hn.find(needle, pos)
        if idx < 0:
            out_of_order.append(t)
        else:
            pos = idx + len(needle)
    return CheckResult(
        type="word_order",
        passed=not out_of_order,
        detail={"missing_or_out_of_order": out_of_order} if out_of_order else {},
    )


def _last_nonempty_line(resp: str) -> str:
    lines = [ln for ln in resp.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _check_answer_in(spec: dict, resp: str, ctx) -> CheckResult:
    _need(spec, "answers")
    answers = spec["answers"]
    if isinstance(answers, str):
        answers = [answers]
    if not isinstance(answers, list):
        raise CheckSpecError("'answers' must be a list")
    which = spec.get("line", "last")
    if which == "last":
        cand = _last_nonempty_line(resp)
    elif which == "first":
        cand = next((ln for ln in resp.splitlines() if ln.strip()), "")
    elif which == "any":
        cand = resp
    else:
        raise CheckSpecError(f"bad line selector {which!r}")
    for a in answers:
        if isinstance(a, str) and a.startswith("re:"):
            if re.search(a[3:], cand.strip()):
                return CheckResult(type="answer_in", passed=True)
            continue
        if norm_text(str(a)) == norm_text(cand):
            return CheckResult(type="answer_in", passed=True)
        if which == "any" and norm_text(str(a)) in norm_text(cand):
            return CheckResult(type="answer_in", passed=True)
    return CheckResult(
        type="answer_in",
        passed=False,
        detail={"line": cand.strip()[:200], "expected_one_of": answers},
    )


def _check_answer_line(spec: dict, resp: str, ctx) -> CheckResult:
    """Last non-empty line must literally equal ``value`` (normalized)."""
    _need(spec, "value")
    cand = _last_nonempty_line(resp)
    ok = norm_text(cand) == norm_text(str(spec["value"]))
    return CheckResult(
        type="answer_line",
        passed=ok,
        detail={} if ok else {"line": cand.strip()[:200]},
    )


# --------------------------------------------------------------------------
# line-structure checks


def _check_every_line_matches(spec: dict, resp: str, ctx) -> CheckResult:
    _need(spec, "pattern")
    pat = re.compile(spec["pattern"])
    lines = [ln for ln in resp.splitlines() if ln.strip()]
    bad = [ln for ln in lines if not pat.match(ln.strip())]
    n = spec.get("count")
    detail: dict[str, Any] = {}
    ok = not bad
    if bad:
        detail["bad_lines"] = bad[:5]
    if n is not None and len(lines) != int(n):
        ok = False
        detail["line_count"] = len(lines)
        detail["expected_count"] = int(n)
    return CheckResult(type="every_line_matches", passed=ok, detail=detail)


def _check_only_lines_with_prefix(spec: dict, resp: str, ctx) -> CheckResult:
    _need(spec, "prefix")
    prefix = spec["prefix"]
    lines = [ln for ln in resp.splitlines() if ln.strip()]
    bad = [ln for ln in lines if not ln.lstrip().startswith(prefix)]
    detail: dict[str, Any] = {}
    ok = bool(lines) and not bad
    if bad:
        detail["bad_lines"] = bad[:5]
    n = spec.get("count")
    if n is not None and len(lines) != int(n):
        ok = False
        detail["line_count"] = len(lines)
        detail["expected_count"] = int(n)
    if not lines:
        detail["empty"] = True
    return CheckResult(type="only_lines_with_prefix", passed=ok, detail=detail)


# --------------------------------------------------------------------------
# size checks


_COUNTERS: dict[str, Callable[[str], int]] = {
    "chars": len,
    "words": word_count,
    "lines": line_count,
    "sentences": sentence_count,
}


def _check_count(spec: dict, resp: str, ctx) -> CheckResult:
    unit = spec.get("unit", "words")
    if unit not in _COUNTERS:
        raise CheckSpecError(f"bad count unit {unit!r}")
    n = _COUNTERS[unit](resp)
    lo = spec.get("min")
    hi = spec.get("max")
    eq = spec.get("eq")
    if lo is None and hi is None and eq is None:
        raise CheckSpecError("count check needs min/max/eq")
    ok = True
    if eq is not None:
        ok = n == int(eq)
    if lo is not None:
        ok = ok and n >= int(lo)
    if hi is not None:
        ok = ok and n <= int(hi)
    return CheckResult(
        type="count",
        passed=ok,
        detail={"unit": unit, "measured": n, "min": lo, "max": hi, "eq": eq},
    )


# --------------------------------------------------------------------------
# boundary / regex


def _edge_strip(s: str) -> str:
    return s.strip().strip(" \t\"'()[]{}.,;:!?")


def _check_starts_with(spec: dict, resp: str, ctx) -> CheckResult:
    _need(spec, "value")
    ok = _edge_strip(norm_text(resp, keep_punct=True)).startswith(
        _edge_strip(norm_text(str(spec["value"]), keep_punct=True))
    )
    return CheckResult(type="starts_with", passed=ok)


def _check_ends_with(spec: dict, resp: str, ctx) -> CheckResult:
    _need(spec, "value")
    ok = _edge_strip(norm_text(resp, keep_punct=True)).endswith(
        _edge_strip(norm_text(str(spec["value"]), keep_punct=True))
    )
    return CheckResult(type="ends_with", passed=ok)


def _check_regex(spec: dict, resp: str, ctx) -> CheckResult:
    _need(spec, "pattern")
    scope = spec.get("scope", "all")
    target = resp if scope == "all" else _last_nonempty_line(resp)
    full = spec.get("full", False)
    m = (
        re.fullmatch(spec["pattern"], target.strip())
        if full
        else re.search(spec["pattern"], target)
    )
    return CheckResult(
        type="regex",
        passed=m is not None,
        detail={} if m else {"pattern": spec["pattern"], "scope": scope},
    )


# --------------------------------------------------------------------------
# JSON field extraction


def _balanced_json_objects(text: str) -> list[dict]:
    """Yield dicts parsed from balanced ``{...}`` blocks, string-aware."""
    objs: list[dict] = []
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0:
                    chunk = text[start : i + 1]
                    try:
                        val = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(val, dict):
                        objs.append(val)
    return objs


def extract_json(text: str) -> dict | None:
    t = text.strip()
    # strip common code fences first
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", t, re.DOTALL)
    if m:
        try:
            v = json.loads(m.group(1))
            if isinstance(v, dict):
                return v
        except json.JSONDecodeError:
            pass
    if t.startswith("{"):
        try:
            v = json.loads(t)
            if isinstance(v, dict):
                return v
        except json.JSONDecodeError:
            pass
    objs = _balanced_json_objects(t)
    return objs[0] if objs else None


def _flatten(d: dict, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


def _norm_key(k: object) -> str:
    """Normalize a JSON field name for comparison (keeps dots)."""
    return tr_lower(str(k)).strip()


def _values_equal(expected: Any, actual: Any) -> bool:
    if expected is None:
        return actual is None
    en, an = to_number(expected), to_number(actual)
    if en is not None and an is not None:
        return abs(en - an) < 0.01
    ed, ad = to_date_iso(str(expected)), to_date_iso(str(actual))
    if ed and ad:
        return ed == ad
    return norm_text(str(expected)) == norm_text(str(actual))


def _check_json_fields(spec: dict, resp: str, ctx) -> CheckResult:
    expected = spec.get("expected")
    if expected is None:
        expected = getattr(ctx, "expected", None)
    if not isinstance(expected, dict):
        raise CheckSpecError("json_fields needs a mapping 'expected'")
    required = spec.get("required")
    strict = bool(spec.get("strict", False))
    data = extract_json(resp)
    if data is None:
        return CheckResult(
            type="json_fields", passed=False, detail={"error": "no_json"}
        )
    flat_got = {_norm_key(k): v for k, v in _flatten(data).items()}
    flat_exp = {_norm_key(k): v for k, v in _flatten(expected).items()}
    matched, missed = [], []
    for k, ev in flat_exp.items():
        got = flat_got.get(k)
        if got is None:
            for gk, gv in flat_got.items():
                if gk.endswith("." + k):
                    got = gv
                    break
        if got is not None and _values_equal(ev, got):
            matched.append(k)
        else:
            missed.append(k)
    total = len(flat_exp)
    ratio = len(matched) / total if total else 0.0
    if required:
        need = {_norm_key(r) for r in required}
        ok = all(r in matched for r in need)
    else:
        ok = not missed
    return CheckResult(
        type="json_fields",
        passed=ok,
        fraction=ratio,
        detail={"matched": matched, "missed": missed},
    )


# --------------------------------------------------------------------------
# language heuristic


def _check_turkish_share(spec: dict, resp: str, ctx) -> CheckResult:
    min_share = float(spec.get("min", 0.6))
    toks = [norm_text(w) for w in words(resp)]
    toks = [t for t in toks if t and not t.isdigit()]
    if not toks:
        return CheckResult(
            type="turkish_share", passed=False, detail={"tokens": 0}
        )
    hits = sum(1 for t in toks if t in TURKISH_WORDS or has_turkish_char(t))
    share = hits / len(toks)
    return CheckResult(
        type="turkish_share",
        passed=share >= min_share,
        fraction=round(share, 4),
        detail={"share": round(share, 3), "min": min_share, "tokens": len(toks)},
    )


# --------------------------------------------------------------------------
# refusal detector

_REFUSAL_PATTERNS = [
    "üzgünüm ama yardımcı olamam",
    "yardımcı olamam",
    "bunu yapamam",
    "i can't help",
    "i cannot help",
    "i can't assist",
    "i cannot assist",
    "as an ai language model",
]


def _check_no_refusal(spec: dict, resp: str, ctx) -> CheckResult:
    hn = norm_text(resp, keep_punct=True)
    found = [p for p in _REFUSAL_PATTERNS if p in hn]
    return CheckResult(
        type="no_refusal",
        passed=not found,
        detail={"found": found} if found else {},
    )


# --------------------------------------------------------------------------
# canonical written forms (spelling corrections)


def _check_written_form(spec: dict, resp: str, ctx) -> CheckResult:
    """Correct vs incorrect written forms in one check.

    ``correct``: term(s) that must appear after normalization.
    ``incorrect``: optional term(s) that must NOT appear — typically the
    misspellings the task asked the model to fix. A single substring
    check is not enough for "rewrite correctly" tasks, since a bad
    response can both contain the fix and keep the error.

    Score = (found correct - found incorrect) / len(correct), floored
    at 0; the check passes only at 1.0.
    """
    correct = spec.get("correct")
    if isinstance(correct, str):
        correct = [correct]
    if not correct or not all(isinstance(t, str) for t in correct):
        raise CheckSpecError("written_form needs 'correct' term(s)")
    incorrect = spec.get("incorrect") or []
    if isinstance(incorrect, str):
        incorrect = [incorrect]
    hn = norm_text(resp)
    found = [t for t in correct if norm_text(t) in hn]
    missing = [t for t in correct if norm_text(t) not in hn]
    bad = [t for t in incorrect if norm_text(t) in hn]
    frac = max(0.0, (len(found) - len(bad)) / len(correct))
    return CheckResult(
        type="written_form",
        passed=frac >= 0.999,
        fraction=round(frac, 4),
        detail={
            "missing": missing,
            "bad_found": bad,
        } if (missing or bad) else {},
    )

# --------------------------------------------------------------------------
# Turkish orthography rules (deterministic scanners in spelling.py)


def _check_spelling_rules(spec: dict, resp: str, ctx) -> CheckResult:
    """Scan the response for unambiguous Turkish spelling violations.

    Rules (subset via ``rules:``):
      - ``mi_attached``:   question particle glued to a word ("gelmişmi").
      - ``mi_harmony``:    separate particle with wrong vowel ("Geldim mı").
      - ``ki_separate``:   "-ki" left separate after locative/ablative or
                           time adverbial ("evde ki", "bugün ki").
      - ``compound_traps``: canonical fused-form misspellings ("herşey",
                           "yanlız", "yada", "dahada"...).

    ``allow:`` lists extra tokens/stems to skip (proper nouns, jargon).
    ``max_violations`` tolerates N hits (default 0). Partial credit:
    each violation costs 25% of the check.
    """
    names = spec.get("rules")
    if names is None:
        scanners = list(SCANNERS.values())
    else:
        if isinstance(names, str):
            names = [names]
        bad = [n for n in names if n not in SCANNERS]
        if bad:
            raise CheckSpecError(
                f"unknown spelling rule(s) {bad!r} "
                f"(known: {', '.join(sorted(SCANNERS))})"
            )
        scanners = [SCANNERS[n] for n in names]
    allow = spec.get("allow") or []
    if isinstance(allow, str):
        allow = [allow]
    if not all(isinstance(a, str) for a in allow):
        raise CheckSpecError("spelling_rules 'allow' must be string(s)")
    allow_set = {norm_text(a) for a in allow}
    max_v = int(spec.get("max_violations", 0))

    violations: list[str] = []
    for scan in scanners:
        violations.extend(scan(resp, allow_set))
    n = len(violations)
    frac = max(0.0, 1.0 - 0.25 * n)
    return CheckResult(
        type="spelling_rules",
        passed=n <= max_v,
        fraction=round(frac, 4),
        detail={"violations": violations[:12], "count": n}
        if n else {},
    )



# --------------------------------------------------------------------------
# registry


_CHECK_FN = {
    "contains": _check_contains,
    "not_contains": _check_not_contains,
    "word_order": _check_word_order,
    "answer_in": _check_answer_in,
    "answer_line": _check_answer_line,
    "every_line_matches": _check_every_line_matches,
    "only_lines_with_prefix": _check_only_lines_with_prefix,
    "count": _check_count,
    "starts_with": _check_starts_with,
    "ends_with": _check_ends_with,
    "regex": _check_regex,
    "json_fields": _check_json_fields,
    "turkish_share": _check_turkish_share,
    "no_refusal": _check_no_refusal,
    "written_form": _check_written_form,
    "spelling_rules": _check_spelling_rules,
}


def check_types() -> list[str]:
    return sorted(_CHECK_FN)


def evaluate_check(
    spec: dict, response: str, task: Task | None = None
) -> CheckResult:
    t = spec.get("type")
    fn = _CHECK_FN.get(t)
    if fn is None:
        raise CheckSpecError(f"unknown check type {t!r}")
    return fn(spec, response, task)


def score_task(task: Task, response: str) -> list[CheckResult]:
    return [evaluate_check(c, response, task) for c in task.checks]


def task_score_value(results: Iterable[CheckResult]) -> float:
    rs = list(results)
    if not rs:
        return 0.0
    # passing check scores 1.0; a failing check scores its partial fraction
    # (0.0 unless the check set one, e.g. json_fields partial credit)
    total = sum((1.0 if r.passed else max(0.0, r.fraction or 0.0)) for r in rs)
    return total / len(rs)


def validate_check_specs(tasks: Iterable[Task]) -> None:
    """Fail fast on unknown check types / obviously bad params."""
    for t in tasks:
        for i, c in enumerate(t.checks):
            ctype = c.get("type")
            if ctype not in _CHECK_FN:
                raise CheckSpecError(
                    f"{t.id}: unknown check type {ctype!r} "
                    f"(known: {', '.join(check_types())})"
                )
            try:
                # smoke-run against a placeholder response to surface missing
                # required params early; the result itself is discarded
                _CHECK_FN[ctype](c, "x", t)
            except CheckSpecError:
                raise
            except Exception as e:  # pragma: no cover - defensive
                raise CheckSpecError(
                    f"{t.id}: check {i} ({ctype}) spec error: {e}"
                ) from e
