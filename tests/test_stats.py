"""Tests for the deterministic bootstrap CI helper."""

import pytest

from turkce_karne.stats import bootstrap_mean_ci


def test_deterministic_same_input_same_interval():
    groups = [[0.0], [1.0], [1.0], [0.5], [1.0], [0.0], [1.0], [0.75]]
    a = bootstrap_mean_ci(groups)
    b = bootstrap_mean_ci(groups)
    assert a == b


def test_seed_depends_on_data():
    g1 = [[0.0], [1.0], [1.0], [0.0]]
    g2 = [[0.0], [1.0], [1.0], [1.0]]
    # different data -> different resample stream -> (almost surely)
    # different interval; at minimum the helper must not collapse
    a = bootstrap_mean_ci(g1)
    b = bootstrap_mean_ci(g2)
    assert a != b
    assert b[0] > a[0]  # higher-scoring data has a higher bound


def test_all_pass_gives_degenerate_interval():
    lo, hi = bootstrap_mean_ci([[1.0]] * 10)
    assert lo == pytest.approx(1.0)
    assert hi == pytest.approx(1.0)


def test_empty_returns_none():
    assert bootstrap_mean_ci([]) is None
    assert bootstrap_mean_ci([[], []]) is None


def test_bounds_within_data_range_and_ordered():
    groups = [[0.2], [0.4], [0.9], [0.1], [0.7], [0.5]]
    lo, hi = bootstrap_mean_ci(groups)
    assert 0.0 <= lo <= hi <= 1.0
    # interval should bracket the sample mean loosely for smooth data
    mean = sum(g[0] for g in groups) / len(groups)
    assert lo <= mean <= hi


def test_clusters_stay_together():
    # three tasks x three reps each; reps inside a task are correlated,
    # so clustering them must not shrink the interval below the
    # between-task spread (iid flattening would)
    clustered = [[1.0, 1.0, 1.0], [0.0, 0.0, 0.0], [0.5, 0.5, 0.5]]
    flat = [[1.0], [1.0], [1.0], [0.0], [0.0], [0.0], [0.5], [0.5], [0.5]]
    c_lo, c_hi = bootstrap_mean_ci(clustered)
    f_lo, f_hi = bootstrap_mean_ci(flat)
    assert (c_hi - c_lo) >= (f_hi - f_lo)
