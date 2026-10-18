"""Paired comparison of two result JSONs (same task set assumed).

A task "passes" when its score reaches 1.0 (all checks, or full blend).
Improvement = fail in A, pass in B; regression = pass in A, fail in B.
Significance uses McNemar's test on the discordant pairs: exact
two-sided binomial test when fewer than 25 flips, chi-square with
continuity correction otherwise.
"""

from __future__ import annotations

import math

PASS_THRESHOLD = 0.999


def _norm_runs(a: dict, b: dict) -> tuple[dict, dict]:
    ta = {t["id"]: t for t in a.get("tasks", [])}
    tb = {t["id"]: t for t in b.get("tasks", [])}
    return ta, tb


def _binom_two_sided(k: int, n: int) -> float:
    """Two-sided binomial test p-value, p=0.5, by summing terms with
    probability <= P(X=k) (standard 'probability of the observed or more
    extreme' form; for p=0.5 that is the symmetric tail sum)."""
    if n == 0:
        return 1.0
    lo = min(k, n - k)
    hi = n - lo
    # P(X <= lo or X >= hi) with p = 0.5
    tail = sum(math.comb(n, i) for i in range(lo + 1))
    tail += sum(math.comb(n, i) for i in range(hi, n + 1))
    return min(1.0, tail / (2**n))


def _chi2_sf_1df(x: float) -> float:
    """Survival function of chi-square with 1 df = 2*(1-Phi(sqrt(x)))."""
    return math.erfc(math.sqrt(x / 2.0))


def mcnemar_pvalue(improvements: int, regressions: int) -> tuple[float, str]:
    """Return (p_value, method). method is 'exact' or 'chi2_cc'."""
    b, c = improvements, regressions
    n = b + c
    if n == 0:
        return 1.0, "none"
    if n < 25:
        return _binom_two_sided(b, n), "exact"
    chi2 = (abs(b - c) - 1) ** 2 / n  # continuity-corrected
    return _chi2_sf_1df(chi2), "chi2_cc"


def _check_flip(ca: dict, cb: dict) -> str | None:
    """Verdict flip between two check dicts paired by position.

    Returns None when verdicts agree (or a ``fraction`` moved without a
    pass/fail change — score deltas, not flips).
    """
    pa, pb = bool(ca.get("passed")), bool(cb.get("passed"))
    if pa == pb:
        return None
    return "improve" if pb else "regress"


def compare_runs(a: dict, b: dict, *, include_checks: bool = False) -> dict:
    """Compare results dict B against baseline A (B is the 'new' run).

    Returns a JSON-serializable report; ``a``/``b`` tasks are paired by
    task id. Tasks present in only one run are listed under
    ``only_in_*``. With ``include_checks`` each task row also carries a
    ``checks`` list pairing the two runs' check verdicts by position —
    a check entry notes its type, pass/fail in A and B, and the flip
    direction; ``type_changed`` marks spec drift between runs.
    """
    ta, tb = _norm_runs(a, b)
    common = sorted(set(ta) & set(tb))
    rows = []
    improvements = regressions = 0
    deltas: list[float] = []
    by_cat: dict[str, dict] = {}
    n_check_flips = 0
    for tid in common:
        sa = ta[tid].get("score", 0.0)
        sb = tb[tid].get("score", 0.0)
        pa, pb = sa >= PASS_THRESHOLD, sb >= PASS_THRESHOLD
        delta = sb - sa
        deltas.append(delta)
        if not pa and pb:
            improvements += 1
            flip = "improve"
        elif pa and not pb:
            regressions += 1
            flip = "regress"
        elif abs(delta) > 1e-9:
            flip = "delta"
        else:
            flip = "same"
        cat = ta[tid].get("category", "")
        agg = by_cat.setdefault(cat, {"a": 0.0, "b": 0.0, "n": 0})
        agg["a"] += sa
        agg["b"] += sb
        agg["n"] += 1
        row = {
            "id": tid,
            "category": cat,
            "a": round(sa, 4),
            "b": round(sb, 4),
            "delta": round(delta, 4),
            "flip": flip,
        }
        if include_checks:
            cks = []
            ca_list = ta[tid].get("checks") or []
            cb_list = tb[tid].get("checks") or []
            for i, (ca, cb) in enumerate(zip(ca_list, cb_list)):
                cf = _check_flip(ca, cb)
                if cf is not None:
                    n_check_flips += 1
                entry: dict = {
                    "i": i,
                    "type": cb.get("type") or ca.get("type"),
                    "a": bool(ca.get("passed")),
                    "b": bool(cb.get("passed")),
                }
                if cf:
                    entry["flip"] = cf
                if ca.get("type") != cb.get("type"):
                    entry["type_changed"] = True
                cks.append(entry)
            if len(ca_list) != len(cb_list):
                row["checks_len_changed"] = [len(ca_list), len(cb_list)]
            if cks:
                row["checks"] = cks
        rows.append(row)
    p, method = mcnemar_pvalue(improvements, regressions)
    cat_rows = {
        c: {
            "a": round(v["a"] / v["n"], 4),
            "b": round(v["b"] / v["n"], 4),
            "delta": round((v["b"] - v["a"]) / v["n"], 4),
            "n": v["n"],
        }
        for c, v in sorted(by_cat.items())
    }
    # re-sort: flips first (regress, improve, delta), then same
    order = {"regress": 0, "improve": 1, "delta": 2, "same": 3}
    rows.sort(key=lambda r: (order[r["flip"]], -abs(r["delta"]), r["id"]))
    rep = {
        "a": {
            "model": a.get("model"),
            "label": a.get("label"),
            "run_id": a.get("run_id"),
            "score": a.get("summary", {}).get("score"),
        },
        "b": {
            "model": b.get("model"),
            "label": b.get("label"),
            "run_id": b.get("run_id"),
            "score": b.get("summary", {}).get("score"),
        },
        "n_common": len(common),
        "only_in_a": sorted(set(ta) - set(tb)),
        "only_in_b": sorted(set(tb) - set(ta)),
        "improvements": improvements,
        "regressions": regressions,
        "mean_delta": round(sum(deltas) / len(deltas), 4) if deltas else 0.0,
        "mcnemar": {"p": round(p, 4), "method": method},
        "by_category": cat_rows,
        "tasks": rows,
    }
    if include_checks:
        rep["n_check_flips"] = n_check_flips
    return rep


def format_compare(rep: dict) -> str:
    """Human-readable rendering of :func:`compare_runs` output."""
    an = rep["a"].get("label") or rep["a"].get("model") or "A"
    bn = rep["b"].get("label") or rep["b"].get("model") or "B"
    lines = [
        f"A: {an}  score={rep['a'].get('score')}",
        f"B: {bn}  score={rep['b'].get('score')}",
        f"paired tasks: {rep['n_common']}",
    ]
    if rep["only_in_a"]:
        lines.append(f"only in A ({len(rep['only_in_a'])}): "
                     + ", ".join(rep["only_in_a"][:8])
                     + (" ..." if len(rep["only_in_a"]) > 8 else ""))
    if rep["only_in_b"]:
        lines.append(f"only in B ({len(rep['only_in_b'])}): "
                     + ", ".join(rep["only_in_b"][:8])
                     + (" ..." if len(rep["only_in_b"]) > 8 else ""))
    lines.append("")
    lines.append(
        f"flips: {rep['improvements']} improved, {rep['regressions']} regressed"
        f"   mean delta {rep['mean_delta']:+.4f}"
    )
    m = rep["mcnemar"]
    lines.append(f"McNemar ({m['method']}): p = {m['p']}")
    lines.append("")
    lines.append("by category:")
    for c, v in rep["by_category"].items():
        lines.append(
            f"  {c:<16} {v['a'] * 100:5.1f}% -> {v['b'] * 100:5.1f}%"
            f"  ({v['delta'] * 100:+.1f} pp, n={v['n']})"
        )
    flips = [r for r in rep["tasks"] if r["flip"] in ("regress", "improve")]
    if flips:
        lines.append("")
        lines.append("flipped tasks:")
        for r in flips:
            arrow = "↑" if r["flip"] == "improve" else "↓"
            lines.append(
                f"  {arrow} {r['id']:<44} {r['a'] * 100:5.1f}% -> {r['b'] * 100:5.1f}%"
            )
    if rep.get("n_check_flips"):
        lines.append("")
        lines.append(f"check flips: {rep['n_check_flips']}")
        for r in rep["tasks"]:
            for c in r.get("checks", []):
                if c.get("flip"):
                    arrow = "↑" if c["flip"] == "improve" else "↓"
                    lines.append(
                        f"  {arrow} {r['id']}#{c['i']}"
                        f" [{c.get('type')}]"
                        f"{' (type changed)' if c.get('type_changed') else ''}"
                    )
    return "\n".join(lines)
