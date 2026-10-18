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
    assert "est. tokens:" in out and "fingerprint:" in out


def test_dry_run_prompt_style(capsys):
    rc = main(
        [
            "run",
            "--model", "fake-model",
            "--dataset", "dataset",
            "--tasks", "imla/de-da",
            "--prompt-style", "fewshot",
            "--dry-run",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "style:    fewshot" in out and "selected: 1" in out


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


def test_compare_cli(tmp_path, capsys):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    base = {
        "model": "m1",
        "summary": {"score": 0.5},
        "tasks": [
            {"id": "c/1", "category": "c", "score": 1.0},
            {"id": "c/2", "category": "c", "score": 0.0},
        ],
    }
    new = {
        "model": "m2",
        "summary": {"score": 1.0},
        "tasks": [
            {"id": "c/1", "category": "c", "score": 1.0},
            {"id": "c/2", "category": "c", "score": 1.0},
        ],
    }
    a.write_text(json.dumps(base), encoding="utf-8")
    b.write_text(json.dumps(new), encoding="utf-8")
    rc = main(["compare", str(a), str(b)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 improved" in out and "McNemar" in out

    rc = main(["compare", str(a), str(b), "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["improvements"] == 1


def test_report_md_stdout(tmp_path, capsys):
    res = tmp_path / "res.json"
    res.write_text(
        json.dumps(
            {
                "model": "m1",
                "label": "M-One",
                "summary": {
                    "score": 0.75,
                    "ci95": [0.5, 0.9],
                    "n": 4,
                    "by_category": {"demo": {"score": 0.75, "n": 4}},
                },
                "tasks": [],
            }
        ),
        encoding="utf-8",
    )
    rc = main(["report", str(res), "--format", "md"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "| Model |" in out and "| M-One | 75.0%" in out
    assert "[50.0%, 90.0%]" in out
    assert "| demo |" in out


def test_report_html_requires_out(tmp_path, capsys):
    res = tmp_path / "res.json"
    res.write_text(json.dumps({"model": "m", "summary": {}, "tasks": []}))
    rc = main(["report", str(res)])
    assert rc == 2
    assert "--out" in capsys.readouterr().err


def test_report_html_tolerates_sparse_json(tmp_path, capsys):
    # foreign/older results JSON missing optional summary keys must not
    # crash the renderer (regression: est_cost_usd/score_worst_rep)
    res = tmp_path / "res.json"
    res.write_text(json.dumps({"model": "m", "summary": {"score": 0.5},
                               "tasks": []}), encoding="utf-8")
    out = tmp_path / "card.html"
    rc = main(["report", str(res), "--out", str(out)])
    assert rc == 0
    assert "Leaderboard" in out.read_text()
