"""Small deterministic statistics helpers (bootstrap confidence intervals).

No numpy/scipy: every run of this kit must be byte-reproducible, so the
bootstrap resamples are driven by a ``random.Random`` seeded from a SHA-256
of the (already deterministically ordered) input data. Same results JSON in
-> same interval out.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Sequence

RESAMPLES = 2000
LEVEL = 0.95


def _seed_from(groups: Sequence[Sequence[float]], tag: str) -> int:
    blob = tag + "|" + "|".join(
        ",".join(f"{v:.6f}" for v in g) for g in groups
    )
    return int.from_bytes(
        hashlib.sha256(blob.encode()).digest()[:8], "big"
    )


def bootstrap_mean_ci(
    groups: Sequence[Sequence[float]],
    *,
    level: float = LEVEL,
    resamples: int = RESAMPLES,
    tag: str = "mean",
) -> tuple[float, float] | None:
    """Percentile bootstrap CI for a cluster mean.

    ``groups`` is a sequence of measurement clusters; each resample draws
    whole clusters (not individual values), so pass one group per task when
    scores come in ``--repeat`` reps — flattening reps into one pool would
    understate the variance. Returns ``(low, high)`` or ``None`` for an
    empty input.
    """
    gs = [tuple(g) for g in groups if g]
    if not gs:
        return None
    rng = random.Random(_seed_from(gs, tag))
    means: list[float] = []
    for _ in range(resamples):
        draw = [gs[rng.randrange(len(gs))] for _ in range(len(gs))]
        flat = [v for g in draw for v in g]
        means.append(sum(flat) / len(flat))
    means.sort()
    alpha = 1.0 - level
    lo = means[min(int(alpha / 2 * resamples), resamples - 1)]
    hi = means[min(int((1 - alpha / 2) * resamples), resamples - 1)]
    return lo, hi
