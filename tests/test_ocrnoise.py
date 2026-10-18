"""Seeded OCR-noise generator: determinism + field preservation."""

import json
import pathlib
import random
import subprocess
import sys

import pytest
import yaml

from turkce_karne.checks import evaluate_check
from turkce_karne.model import Task
from turkce_karne.ocrnoise import field_variant, render_document
from turkce_karne.textnorm import norm_text, to_date_iso, to_number

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "gen_ocr_tasks.py"
GENERATED = REPO / "src" / "turkce_karne" / "dataset" / "v1" / "cikartim-ocr.yaml"

FIELDS = {
    "tutar": ("money", 1234.56),
    "tarih": ("date", "2026-10-13"),
    "adet": ("int", 7),
    "unvan": ("name", "Gül Mah. Örnek Ltd."),
    "belge_no": ("code", "GN-2026/0903"),
}
LINES = [
    "MAKBUZ VE GİDER BELGESİ",
    "Belge No: {belge_no}    Tarih: {tarih}",
    "Alan: {unvan}",
    "Tutar: {tutar} TL   Adet: {adet}",
    "İşlem: havale — onay kodu 88412",
]


def test_render_document_is_deterministic():
    a, ea = render_document(FIELDS, LINES, seed="makbuz-v1")
    b, eb = render_document(FIELDS, LINES, seed="makbuz-v1")
    assert a == b and ea == eb
    assert ea == {k: canon for k, (_, canon) in FIELDS.items()}


def test_render_document_seed_changes_bytes():
    # the canonical map stays identical across seeds; the noised text is
    # what must differ somewhere across a handful of seeds
    maps = set()
    texts = {
        render_document(FIELDS, LINES, seed=f"makbuz-v{i}")[0]
        for i in range(8)
    }
    for i in range(8):
        _, exp = render_document(FIELDS, LINES, seed=f"makbuz-v{i}")
        maps.add(tuple(sorted(exp.items())))
    assert len(texts) > 1 and maps == {tuple(sorted(
        {k: c for k, (_, c) in FIELDS.items()}.items()))}


def test_render_document_no_placeholders_left():
    text, _ = render_document(FIELDS, LINES, seed="x")
    assert "{" not in text and "}" not in text


def test_render_document_values_still_recoverable():
    # field-level check: field_variant output must round-trip through
    # to_number / to_date_iso / norm_text back to the canonical value
    rng = random.Random(7)
    for name, (kind, canon) in FIELDS.items():
        for _ in range(20):
            disp = field_variant(canon, kind, rng)
            if kind == "date":
                assert to_date_iso(disp) == canon
            elif kind in ("money", "num"):
                assert to_number(disp) == pytest.approx(float(canon))
            elif kind == "int":
                assert int(disp) == canon
            elif kind in ("name", "text"):
                assert norm_text(disp) == norm_text(str(canon))
            else:  # code, plate — verbatim
                assert disp == str(canon)


def test_render_document_noise_hits_nonfield_text():
    clean, _ = render_document(FIELDS, LINES, seed="makbuz-v1", level=0.0)
    noisy, _ = render_document(FIELDS, LINES, seed="makbuz-v1", level=1.0)
    # fields render identically in both; noise only mutates the text
    # segments, so a difference proves the noise path fired
    assert noisy != clean
    assert "{tutar}" not in noisy and "{tarih}" not in noisy


def test_render_document_zero_level_is_clean_fill():
    text, _ = render_document(FIELDS, LINES, seed="makbuz-v1", level=0.0)
    assert "MAKBUZ VE GİDER BELGESİ" in text
    assert "{belge_no}" not in text


def test_render_document_unknown_field_raises():
    with pytest.raises(ValueError):
        render_document(FIELDS, ["{bilinmeyen}"], seed="x")


def test_generated_file_fresh():
    """scripts/gen_ocr_tasks.py --check must pass against the committed file."""
    rc = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    )
    assert rc.returncode == 0, rc.stderr


def test_generated_tasks_parse_and_check():
    """Generated YAML loads as real tasks and a canonical JSON response
    passes its checks (the noised input still carries recoverable values)."""
    raw = yaml.safe_load(GENERATED.read_text(encoding="utf-8"))
    assert raw["items"], "generated dataset is empty"
    for item in raw["items"]:
        task = Task(
            id=item["id"],
            category=item["category"],
            prompt=item["prompt"],
            input=item.get("input"),
            expected=item.get("expected"),
            checks=item["checks"],
            difficulty=item.get("difficulty", 1),
        )
        # a model that simply returns the canonical values must pass
        resp = json.dumps(task.expected, ensure_ascii=False)
        results = [evaluate_check(c, resp, task) for c in task.checks]
        assert all(r.passed for r in results), (
            f"{task.id}: canonical response fails "
            f"{[r.detail for r in results if not r.passed]}"
        )
        assert "{" not in task.input
