"""Dataset loader + shipped-dataset integrity tests."""

import pathlib

import pytest
import yaml

from turkce_karne.dataset import (
    categories,
    dataset_digest,
    items_digest,
    load_dataset,
)
from turkce_karne.errors import CheckSpecError, DatasetError

REPO = pathlib.Path(__file__).resolve().parents[1]
CANONICAL = REPO / "src" / "turkce_karne" / "dataset"


def test_shipped_dataset_loads():
    tasks = load_dataset(CANONICAL)
    assert len(tasks) >= 24
    cats = categories(tasks)
    assert len(cats) == 8, cats
    for c in [
        "resmi-yazi",
        "eposta",
        "ozet",
        "cikartim",
        "imla",
        "yonerge",
        "ceviri",
        "akl-yurutme",
    ]:
        assert c in cats, f"missing category {c}"


def test_ids_unique_and_prefixed():
    tasks = load_dataset(CANONICAL)
    ids = [t.id for t in tasks]
    assert len(ids) == len(set(ids))
    for t in tasks:
        assert t.id.startswith(t.category + "/")


def test_digest_stable():
    d1 = dataset_digest(CANONICAL)
    d2 = dataset_digest(CANONICAL)
    assert d1 == d2 and len(d1) == 64


def test_root_symlink_matches_package(tmp_path):
    root_link = REPO / "dataset"
    if not root_link.exists():
        pytest.skip("root dataset symlink not present")
    a = dataset_digest(CANONICAL)
    b = dataset_digest(root_link)
    assert a == b


def test_duplicate_id_rejected(tmp_path):
    d = tmp_path / "ds" / "v1"
    d.mkdir(parents=True)
    (d / "x.yaml").write_text(
        """items:
  - id: x/a
    category: x
    prompt: p
    checks: [{type: contains, terms: [a]}]
  - id: x/a
    category: x
    prompt: p2
    checks: [{type: contains, terms: [a]}]
""",
        encoding="utf-8",
    )
    with pytest.raises(DatasetError, match="duplicate"):
        load_dataset(tmp_path / "ds")


def test_bad_check_type_rejected(tmp_path):
    d = tmp_path / "ds" / "v1"
    d.mkdir(parents=True)
    (d / "x.yaml").write_text(
        """items:
  - id: x/a
    category: x
    prompt: p
    checks: [{type: nonexistent_check}]
""",
        encoding="utf-8",
    )
    with pytest.raises(CheckSpecError):
        load_dataset(tmp_path / "ds")


def test_missing_checks_rejected(tmp_path):
    d = tmp_path / "ds" / "v1"
    d.mkdir(parents=True)
    (d / "x.yaml").write_text(
        """items:
  - id: x/a
    category: x
    prompt: p
""",
        encoding="utf-8",
    )
    with pytest.raises(DatasetError):
        load_dataset(tmp_path / "ds")


def test_items_digest_order_independent(tmp_path):
    t = load_dataset(CANONICAL)
    assert items_digest(t) == items_digest(list(reversed(t)))
