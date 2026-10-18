"""Dataset loading, validation and hashing.

Resolution order for the dataset directory:
1. an explicit path passed to ``load_dataset`` / ``--dataset``
2. ``dataset/`` at the current working directory or any parent (repo checkout)
3. the copy bundled inside the installed package
"""

from __future__ import annotations

import hashlib
import re
from importlib import resources
from pathlib import Path
from typing import Iterable

import yaml

from .errors import CheckSpecError, DatasetError
from .model import Task

# check registry is imported lazily inside validate() to avoid a cycle
_ALLOWED_KEYS = {
    "id", "category", "prompt", "input", "expected", "checks",
    "difficulty", "notes",
}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$")
_ID_PREFIX = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SCALAR = (str, int, float, bool, type(None))


def _repo_dataset_dir() -> Path | None:
    here = Path.cwd().resolve()
    for base in (here, *here.parents):
        cand = base / "dataset"
        if cand.is_dir() and any(cand.glob("v*")):
            return cand
    return None


def _bundled_dataset_dir() -> Path | None:
    try:
        root = resources.files("turkce_karne") / "dataset"
        if root.is_dir():
            return Path(str(root))
    except (ModuleNotFoundError, TypeError, FileNotFoundError):
        pass
    return None


def resolve_dataset_dir(path: str | Path | None) -> Path:
    if path is not None:
        p = Path(path).expanduser().resolve()
        if not p.is_dir():
            raise DatasetError(f"dataset path is not a directory: {p}")
        return p
    p = _repo_dataset_dir()
    if p is not None:
        return p
    p = _bundled_dataset_dir()
    if p is not None:
        return p
    raise DatasetError(
        "dataset directory not found (looked for ./dataset and bundled copy)"
    )


def _iter_yaml_files(base: Path, version: str) -> list[Path]:
    vdir = base / version
    if not vdir.is_dir():
        raise DatasetError(f"dataset version not found: {vdir}")
    files = sorted(vdir.glob("*.yaml")) + sorted(vdir.glob("*.yml"))
    if not files:
        raise DatasetError(f"no YAML files in {vdir}")
    return files


def _check_scalars(value, where: str):
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise DatasetError(f"{where}: non-string key {k!r}")
            _check_scalars(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _check_scalars(v, f"{where}[{i}]")
    elif not isinstance(value, _SCALAR):
        raise DatasetError(f"{where}: unsupported value type {type(value).__name__}")


def _validate_task(raw: dict, seen: set[str], source: str) -> Task:
    if not isinstance(raw, dict):
        raise DatasetError(f"{source}: item is not a mapping")
    unknown = set(raw) - _ALLOWED_KEYS
    if unknown:
        raise DatasetError(f"{source}: unknown keys {sorted(unknown)}")
    tid = raw.get("id")
    if not isinstance(tid, str) or not _ID_RE.match(tid):
        raise DatasetError(f"{source}: bad or missing id {tid!r}")
    if tid in seen:
        raise DatasetError(f"duplicate task id: {tid}")
    seen.add(tid)
    category = raw.get("category")
    if not isinstance(category, str) or not _ID_PREFIX.match(category):
        raise DatasetError(f"{source}: bad or missing category for {tid}")
    if not tid.startswith(category + "/"):
        raise DatasetError(
            f"{source}: id {tid} must start with its category '{category}/'"
        )
    prompt = raw.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise DatasetError(f"{source}: missing prompt for {tid}")
    checks = raw.get("checks")
    if not isinstance(checks, list) or not checks:
        raise DatasetError(f"{source}: {tid} needs at least one check")
    for i, chk in enumerate(checks):
        if not isinstance(chk, dict) or "type" not in chk:
            raise CheckSpecError(f"{source}: check {i} of {tid} lacks 'type'")
        _check_scalars(chk, f"{source}:{tid}.checks[{i}]")
    _check_scalars(raw.get("expected"), f"{source}:{tid}.expected")
    difficulty = raw.get("difficulty", 1)
    if not isinstance(difficulty, int) or not 1 <= difficulty <= 5:
        raise DatasetError(f"{source}: {tid} difficulty must be int 1..5")
    inp = raw.get("input")
    if inp is not None and not isinstance(inp, str):
        raise DatasetError(f"{source}: {tid} input must be a string")
    return Task(
        id=tid,
        category=category,
        prompt=prompt.strip(),
        input=inp.strip() if isinstance(inp, str) else None,
        expected=raw.get("expected"),
        checks=checks,
        difficulty=difficulty,
        notes=raw.get("notes"),
    )


def load_dataset(
    path: str | Path | None = None,
    *,
    version: str = "v1",
    validate: bool = True,
) -> list[Task]:
    base = resolve_dataset_dir(path)
    files = _iter_yaml_files(base, version)
    tasks: list[Task] = []
    seen: set[str] = set()
    for f in files:
        if f.name.startswith("_"):
            continue  # sidecar files (exemplars, metadata) hashed but not tasks
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise DatasetError(f"{f.name}: YAML parse error: {e}") from e
        if not isinstance(data, dict) or "items" not in data:
            raise DatasetError(f"{f.name}: expected a mapping with an 'items' list")
        items = data["items"]
        if not isinstance(items, list):
            raise DatasetError(f"{f.name}: 'items' must be a list")
        for raw in items:
            tasks.append(_validate_task(raw, seen, f.name))
    if validate:
        from .checks import validate_check_specs

        validate_check_specs(tasks)
    return tasks


def dataset_digest(path: str | Path | None = None, *, version: str = "v1") -> str:
    """sha256 over the sorted raw bytes of every dataset file."""
    base = resolve_dataset_dir(path)
    h = hashlib.sha256()
    h.update(version.encode())
    for f in _iter_yaml_files(base, version):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def items_digest(tasks: Iterable[Task]) -> str:
    """Stable digest over parsed item content (order independent)."""
    h = hashlib.sha256()
    for t in sorted(tasks, key=lambda t: t.id):
        blob = yaml.safe_dump(
            {
                "id": t.id,
                "category": t.category,
                "prompt": t.prompt,
                "input": t.input,
                "expected": t.expected,
                "checks": t.checks,
                "difficulty": t.difficulty,
            },
            sort_keys=True,
            allow_unicode=True,
        )
        h.update(blob.encode())
    return h.hexdigest()


def categories(tasks: Iterable[Task]) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in tasks:
        out[t.category] = out.get(t.category, 0) + 1
    return dict(sorted(out.items()))


def load_exemplars(
    path: str | Path | None = None,
    *,
    version: str = "v1",
) -> dict[str, dict]:
    """Load few-shot exemplars from ``_exemplars.yaml`` (optional sidecar).

    Returns ``{category: {"user": ..., "assistant": ...}}``; ``"default"``
    is the fallback for categories without a dedicated exemplar. Missing
    file → empty dict (few-shot degrades to zero-shot for that run).
    """
    base = resolve_dataset_dir(path)
    vdir = base / version
    f = vdir / "_exemplars.yaml"
    if not f.is_file():
        return {}
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("exemplars"), dict):
        raise DatasetError(f"{f.name}: expected an 'exemplars' mapping")
    out: dict[str, dict] = {}
    for cat, ex in data["exemplars"].items():
        if not isinstance(cat, str) or not _ID_PREFIX.match(cat) and cat != "default":
            raise DatasetError(f"{f.name}: bad exemplar category {cat!r}")
        if (
            not isinstance(ex, dict)
            or not isinstance(ex.get("user"), str)
            or not isinstance(ex.get("assistant"), str)
        ):
            raise DatasetError(
                f"{f.name}: exemplar {cat!r} needs 'user' and 'assistant' strings"
            )
        out[cat] = {"user": ex["user"], "assistant": ex["assistant"]}
    return out
