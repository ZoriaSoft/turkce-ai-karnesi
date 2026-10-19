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


def test_run_missing_model_fails(monkeypatch):
    monkeypatch.delenv("KARNE_MODEL", raising=False)
    assert main(["run", "--dataset", "dataset"]) == 2


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


def test_compare_cli_single_file_fails(tmp_path, capsys):
    a = tmp_path / "a.json"
    a.write_text(json.dumps({"tasks": []}), encoding="utf-8")
    rc = main(["compare", str(a)])
    assert rc == 2
    assert "at least 2" in capsys.readouterr().err


def test_compare_cli_three_files(tmp_path, capsys):
    def _w(path, model, scores):
        path.write_text(json.dumps({
            "model": model,
            "summary": {"score": sum(scores) / len(scores)},
            "tasks": [
                {"id": f"c/{i+1}", "category": "c", "score": s}
                for i, s in enumerate(scores)
            ],
        }), encoding="utf-8")

    a, b, c = (tmp_path / n for n in ("a.json", "b.json", "c.json"))
    _w(a, "base", [1.0, 0.0])
    _w(b, "better", [1.0, 1.0])
    _w(c, "worse", [0.0, 0.0])
    rc = main(["compare", str(a), str(b), str(c)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "baseline (A): base" in out and "leaderboard" in out
    assert "better" in out and "worse" in out

    rc = main(["compare", str(a), str(b), str(c), "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["baseline"]["name"] == "base"
    assert data["n_runs"] == 3
    assert [e["name"] for e in data["leaderboard"]] == [
        "better", "base", "worse"]
    assert len(data["comparisons"]) == 2


def test_compare_cli_best_baseline(tmp_path, capsys):
    def _w(path, model, scores):
        path.write_text(json.dumps({
            "model": model,
            "summary": {"score": sum(scores) / len(scores)},
            "tasks": [
                {"id": f"c/{i+1}", "category": "c", "score": s}
                for i, s in enumerate(scores)
            ],
        }), encoding="utf-8")

    a, b, c = (tmp_path / n for n in ("a.json", "b.json", "c.json"))
    _w(a, "low", [0.0, 0.0])
    _w(b, "mid", [1.0, 0.0])
    _w(c, "top", [1.0, 1.0])
    # --best picks the highest-scoring file as baseline, not the first
    rc = main(["compare", str(a), str(b), str(c), "--best", "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["baseline"]["name"] == "top"
    assert data["n_runs"] == 3
    assert [e["name"] for e in data["leaderboard"]] == ["top", "mid", "low"]


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


def test_run_model_from_env(dataset_dir, fake_openai, tmp_path, monkeypatch):
    state, base = fake_openai
    monkeypatch.setenv("KARNE_MODEL", "env-model")
    monkeypatch.setenv("KARNE_TEMPERATURE", "0.3")
    out_json = tmp_path / "res.json"
    rc = main(["run", "--base-url", base, "--dataset", str(dataset_dir),
               "--out", str(out_json), "--cache", "off"])
    assert rc == 0
    assert state.requests and all(r["model"] == "env-model" for r in state.requests)
    assert all(r["temperature"] == 0.3 for r in state.requests)


def test_run_without_model_is_usage_error(monkeypatch, capsys):
    monkeypatch.delenv("KARNE_MODEL", raising=False)
    rc = main(["run", "--dry-run"])
    assert rc == 2
    assert "KARNE_MODEL" in capsys.readouterr().err


def test_bad_env_number_is_reported(monkeypatch):
    import pytest

    monkeypatch.setenv("KARNE_TIMEOUT", "soon")
    with pytest.raises(SystemExit, match="KARNE_TIMEOUT"):
        main(["run", "--model", "m", "--dry-run"])


def test_run_all_errors_exits_nonzero(dataset_dir, fake_openai, tmp_path, capsys):
    state, base = fake_openai
    state.fail_next_n = 1000
    state.fail_status = 401
    rc = main(["run", "--model", "m", "--base-url", base,
               "--dataset", str(dataset_dir), "--out", str(tmp_path / "r.json"),
               "--cache", "off", "--max-retries", "0"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "every request errored" in err and "HTTP 401" in err


def test_report_and_compare_missing_file(tmp_path, capsys):
    missing = str(tmp_path / "nope.json")
    assert main(["report", missing, "--format", "md"]) == 2
    assert "no such file" in capsys.readouterr().err
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    assert main(["compare", str(bad), str(bad)]) == 2
    assert "not a results JSON" in capsys.readouterr().err


def test_list_missing_dataset_is_clean_error(tmp_path, capsys):
    rc = main(["list", "--dataset", str(tmp_path / "nowhere")])
    assert rc == 1
    assert "dataset invalid" in capsys.readouterr().err


def test_html_report_escapes_model_output(dataset_dir, fake_openai, tmp_path):
    state, base = fake_openai
    state.default_content = '<script>alert("x")</script> 42'
    out_json = tmp_path / "res.json"
    assert main(["run", "--model", "m", "--base-url", base,
                 "--dataset", str(dataset_dir), "--out", str(out_json),
                 "--cache", "off", "--html"]) == 0
    html = out_json.with_suffix(".html").read_text(encoding="utf-8")
    assert "<script>alert" not in html
    assert "<script>" in html
