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
    return tpl.render(runs=runs, title=title or "turkce-karne scorecard")


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
