"""CLI end-to-end: validate, list, run (fake server), report."""

import json

from turkce_karne.cli import main


def test_validate_ok(capsys):
    rc = main(["validate", "--dataset", "dataset"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK" in out and "items:" in out


def test_list_tasks(capsys):
    rc = main(["list", "--dataset", "dataset", "--categories", "imla"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "imla/" in out


def test_dry_run(capsys):
    rc = main(
        [
            "run",
            "--model", "fake-model",
            "--dataset", "dataset",
            "--categories", "imla",
            "--dry-run",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "selected:" in out and "imla/" in out


def test_run_then_report(dataset_dir, fake_openai, tmp_path, capsys):
    state, base = fake_openai
    state.add_rule("Bir sayı yaz", "42")
    state.add_rule("Cevap: 7", "Cevap: 7")
    out_json = tmp_path / "res.json"
    rc = main(
        [
            "run",
            "--model", "fake-model",
            "--base-url", base,
            "--dataset", str(dataset_dir),
            "--out", str(out_json),
            "--cache", "off",
            "--concurrency", "1",
        ]
    )
    assert rc == 0
    assert out_json.exists()
    data = json.loads(out_json.read_text())
    assert data["summary"]["score"] == 1.0

    out_html = tmp_path / "card.html"
    rc = main(["report", str(out_json), "--out", str(out_html)])
    assert rc == 0
    assert out_html.exists()
    assert "Leaderboard" in out_html.read_text()


def test_run_missing_model_fails():
    try:
        main(["run", "--dataset", "dataset"])
    except SystemExit as e:
        assert e.code != 0
    else:  # pragma: no cover
        raise AssertionError("expected argparse to exit")
