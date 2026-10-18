"""Tests for the paired run comparison."""

import pytest

from turkce_karne.compare import (
    _binom_two_sided,
    compare_runs,
    format_compare,
    mcnemar_pvalue,
)


def _run(model, tasks):
    """Minimal results dict for compare tests."""
    return {
        "model": model,
        "label": model,
        "run_id": "r-" + model,
        "summary": {"score": sum(s for _, s in tasks) / max(1, len(tasks))},
        "tasks": [
            {"id": tid, "category": tid.split("/")[0], "score": s, "checks": []}
            for tid, s in tasks
        ],
    }


def test_mcnemar_exact_known_value():
    # b=9, c=1 -> two-sided exact p = 2*11/1024 = 0.02148
    p, method = mcnemar_pvalue(9, 1)
    assert method == "exact"
    assert p == pytest.approx(0.0215, abs=1e-4)


def test_mcnemar_no_discordance():
    p, method = mcnemar_pvalue(0, 0)
    assert p == 1.0 and method == "none"


def test_mcnemar_chi2_for_large_n():
    p, method = mcnemar_pvalue(20, 5)
    assert method == "chi2_cc"
    # chi2 = (20-5-1)^2 / 25 = 7.84 -> p ~= 0.0051
    assert p == pytest.approx(0.0051, abs=5e-4)


def test_binom_boundaries():
    assert _binom_two_sided(0, 0) == 1.0
    assert _binom_two_sided(5, 5) == pytest.approx(0.0625)  # 2/32
    assert 0 < _binom_two_sided(0, 10) < 0.01


def test_compare_counts_flips():
    a = _run("A", [("c/one", 1.0), ("c/two", 0.5), ("c/three", 1.0)])
    b = _run("B", [("c/one", 1.0), ("c/two", 1.0), ("c/three", 0.0)])
    rep = compare_runs(a, b)
    assert rep["n_common"] == 3
    assert rep["improvements"] == 1  # c/two 0.5 -> 1.0
    assert rep["regressions"] == 1  # c/three 1.0 -> 0.0
    assert rep["mean_delta"] == pytest.approx(-0.1667)
    by_id = {r["id"]: r for r in rep["tasks"]}
    assert by_id["c/two"]["flip"] == "improve"
    assert by_id["c/three"]["flip"] == "regress"
    assert by_id["c/one"]["flip"] == "same"


def test_compare_lists_disjoint_tasks():
    a = _run("A", [("c/x", 1.0), ("c/a-only", 1.0)])
    b = _run("B", [("c/x", 1.0), ("c/b-only", 0.0)])
    rep = compare_runs(a, b)
    assert rep["only_in_a"] == ["c/a-only"]
    assert rep["only_in_b"] == ["c/b-only"]
    assert rep["n_common"] == 1


def test_compare_partial_scores_no_flip():
    # 0.9 -> 0.1 is a big delta but neither side passes
    a = _run("A", [("c/t", 0.9)])
    b = _run("B", [("c/t", 0.1)])
    rep = compare_runs(a, b)
    assert rep["improvements"] == 0 and rep["regressions"] == 0
    assert rep["tasks"][0]["flip"] == "delta"


def test_by_category_aggregates():
    a = _run("A", [("x/1", 1.0), ("x/2", 0.0), ("y/1", 0.5)])
    b = _run("B", [("x/1", 1.0), ("x/2", 1.0), ("y/1", 0.5)])
    rep = compare_runs(a, b)
    assert rep["by_category"]["x"]["delta"] == pytest.approx(0.5)
    assert rep["by_category"]["y"]["delta"] == 0.0


def test_format_compare_text():
    a = _run("base", [("c/t1", 1.0), ("c/t2", 0.0)])
    b = _run("new", [("c/t1", 1.0), ("c/t2", 1.0)])
    out = format_compare(compare_runs(a, b))
    assert "1 improved" in out and "0 regressed" in out
    assert "McNemar" in out and "c/t2" in out
