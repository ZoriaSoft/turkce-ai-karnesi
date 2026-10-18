"""Static HTML scorecard renderer (Jinja2, zero external assets)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from jinja2 import Environment, PackageLoader, select_autoescape

_env = Environment(
    loader=PackageLoader("turkce_karne", "templates"),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)

PASS = "pass"
FAIL = "fail"
PARTIAL = "partial"


def _task_state(t: dict) -> str:
    if t.get("error"):
        return "error"
    s = t.get("score", 0)
    if s >= 0.999:
        return PASS
    if s <= 0.001:
        return FAIL
    return PARTIAL


def _check_state(c: dict) -> str:
    return PASS if c.get("passed") else FAIL


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def render_html(runs: dict | list[dict], *, title: str | None = None) -> str:
    if isinstance(runs, dict):
        runs = [runs]
    runs = sorted(
        runs, key=lambda r: r.get("summary", {}).get("score", 0), reverse=True
    )
    for r in runs:
        for t in r.get("tasks", []):
            t["_state"] = _task_state(t)
            for c in t.get("checks", []):
                c["_state"] = _check_state(c)
        r.setdefault("summary", {})["_pct"] = _pct(
            r.get("summary", {}).get("score", 0)
        )
        for c in r.get("summary", {}).get("by_category", {}).values():
            c["_pct"] = _pct(c.get("score", 0))
    tpl = _env.get_template("scorecard.html.j2")
    return tpl.render(
        runs=runs,
        title=title or "turkce-karne scorecard",
        chart=_category_chart(runs),
    )


# ---------------------------------------------------------------------------
# inline-SVG per-category comparison chart

_CHART_COLORS = [
    "#4c9be0", "#35c46f", "#e0b53c", "#e4574c", "#9a6fd0", "#4cc4b9",
    "#d97fb0", "#8fb14c",
]


def _category_chart(runs: list[dict]) -> dict | None:
    """Build a grouped horizontal-bar chart spec for the template.

    Returns {cats: [...], runs: [...], bars: {cat: {run_i: score}},
    colors: [...]} or None when there is nothing worth plotting (no
    categories, or a single run with a single category).
    """
    cats: list[str] = []
    for r in runs:
        for c in r.get("summary", {}).get("by_category", {}):
            if c not in cats:
                cats.append(c)
    cats.sort()
    if not cats or (len(runs) < 2 and len(cats) < 2):
        return None
    bars: dict[str, dict[int, float]] = {c: {} for c in cats}
    for i, r in enumerate(runs):
        for c, cs in r.get("summary", {}).get("by_category", {}).items():
            bars[c][i] = cs.get("score", 0)
    labels = [
        (r.get("label") or r.get("model") or f"run {i + 1}")[:24]
        for i, r in enumerate(runs)
    ]
    return {
        "cats": cats,
        "labels": labels,
        "bars": bars,
        "colors": _CHART_COLORS[: len(runs)],
        "n_runs": len(runs),
    }


def write_html(
    runs: dict | list[dict], out_path: str | Path, *, title: str | None = None
) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_html(runs, title=title), encoding="utf-8")
    return p


def runs_from_files(paths: Iterable[str | Path]) -> list[dict]:
    out = []
    for p in paths:
        out.append(json.loads(Path(p).read_text(encoding="utf-8")))
    return out
