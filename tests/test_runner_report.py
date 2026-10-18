"""End-to-end runner and report tests using the fake server."""

import json

import pytest

from turkce_karne.client import OpenAICompatClient
from turkce_karne.report import render_html, render_markdown, write_html
from turkce_karne.runner import RunConfig, load_results, run_eval, save_results


def _run(dataset_dir, base, state, **kw):
    cfg = RunConfig(
        model="fake-model",
        dataset_path=str(dataset_dir),
        cache_dir=None,
        **{"concurrency": 1, **kw},
    )
    client = OpenAICompatClient(base, timeout=10)
    results = run_eval(cfg, client=client)
    client.close()
    return results


def test_end_to_end(dataset_dir, fake_openai):
    state, base = fake_openai
    state.add_rule("Bir sayı yaz", "Cevap: 42")
    state.add_rule("Cevap: 7", "düşünüyorum\nCevap: 7")
    results = _run(dataset_dir, base, state)
    assert results["summary"]["n"] == 2
    assert results["summary"]["score"] == pytest.approx(1.0)
    by_id = {t["id"]: t for t in results["tasks"]}
    assert by_id["demo/t1"]["score"] == 1.0
    assert by_id["demo/t2"]["score"] == 1.0
    assert results["dataset"]["sha256"]
    assert results["config_fingerprint"]


def test_partial_score(dataset_dir, fake_openai):
    state, base = fake_openai
    state.add_rule("Bir sayı yaz", "hiçbir şey")
    state.add_rule("Cevap: 7", "Cevap: 7")  # t2: answer ok, words>=1 ok
    results = _run(dataset_dir, base, state)
    by_id = {t["id"]: t for t in results["tasks"]}
    assert by_id["demo/t1"]["score"] == 0.0
    assert by_id["demo/t2"]["score"] == 1.0
    assert results["summary"]["score"] == pytest.approx(0.5)


def test_error_task_scores_zero(dataset_dir, fake_openai):
    state, base = fake_openai
    state.fail_next_n = 2
    state.fail_status = 500
    client = OpenAICompatClient(base, timeout=10, max_retries=0)
    cfg = RunConfig(
        model="fake-model", dataset_path=str(dataset_dir), cache_dir=None
    )
    results = run_eval(cfg, client=client)
    client.close()
    assert results["summary"]["errors"] == 2
    assert results["summary"]["score"] == 0.0


def test_results_json_roundtrip(dataset_dir, fake_openai, tmp_path):
    state, base = fake_openai
    results = _run(dataset_dir, base, state)
    out = tmp_path / "res.json"
    save_results(results, out)
    loaded = load_results(out)
    assert loaded["model"] == "fake-model"
    assert loaded["dataset"]["n_run"] == 2
    # JSON-serializable without custom encoders
    json.dumps(loaded)


def test_html_report_renders(dataset_dir, fake_openai, tmp_path):
    state, base = fake_openai
    results = _run(dataset_dir, base, state)
    html = render_html(results)
    assert "<html" in html and "demo/t1" in html
    assert "Leaderboard" in html
    out = write_html(results, tmp_path / "card.html")
    assert out.exists() and out.stat().st_size > 1000


def test_multi_run_leaderboard_sorted(dataset_dir, fake_openai):
    state, base = fake_openai
    r1 = _run(dataset_dir, base, state)
    # second "run" with worse score via failing state
    state.fail_next_n = 99
    client = OpenAICompatClient(base, timeout=10, max_retries=0)
    cfg = RunConfig(
        model="fake-model", dataset_path=str(dataset_dir), cache_dir=None,
        label="failing",
    )
    r2 = run_eval(cfg, client=client)
    client.close()
    html = render_html([r2, r1])
    # first leaderboard row should be the better run
    assert html.find("fake-model") < html.find("failing")


def test_sample_seeded(dataset_dir, fake_openai):
    state, base = fake_openai
    cfg = RunConfig(
        model="fake-model",
        dataset_path=str(dataset_dir),
        sample=1,
        seed=7,
        cache_dir=None,
    )
    client = OpenAICompatClient(base, timeout=10)
    r1 = run_eval(cfg, client=client)
    client.close()
    assert r1["summary"]["n"] == 1


def test_system_prompt_sent(dataset_dir, fake_openai):
    state, base = fake_openai
    cfg = RunConfig(
        model="fake-model",
        dataset_path=str(dataset_dir),
        system_prompt="ÖZEL SISTEM",
        cache_dir=None,
    )
    client = OpenAICompatClient(base, timeout=10)
    run_eval(cfg, client=client)
    client.close()
    msgs = state.requests[0]["messages"]
    assert msgs[0]["role"] == "system" and msgs[0]["content"] == "ÖZEL SISTEM"


def test_prompt_style_zero_is_default(dataset_dir, fake_openai):
    state, base = fake_openai
    cfg = RunConfig(
        model="fake-model", dataset_path=str(dataset_dir), cache_dir=None,
    )
    client = OpenAICompatClient(base, timeout=10)
    run_eval(cfg, client=client)
    client.close()
    msgs = state.requests[0]["messages"]
    assert [m["role"] for m in msgs] == ["system", "user"]


def test_prompt_style_cot_appends_suffix(dataset_dir, fake_openai):
    state, base = fake_openai
    cfg = RunConfig(
        model="fake-model",
        dataset_path=str(dataset_dir),
        prompt_style="cot",
        cache_dir=None,
    )
    client = OpenAICompatClient(base, timeout=10)
    run_eval(cfg, client=client)
    client.close()
    user = state.requests[0]["messages"][-1]["content"]
    assert "adım adım" in user


def test_prompt_style_fewshot_inserts_exemplar(dataset_dir, fake_openai):
    state, base = fake_openai
    # write a sidecar exemplars file into the temp dataset
    import pathlib

    (pathlib.Path(dataset_dir) / "v1" / "_exemplars.yaml").write_text(
        """exemplars:
  demo:
    user: "ÖRNEK SORU"
    assistant: "ÖRNEK CEVAP"
""",
        encoding="utf-8",
    )
    cfg = RunConfig(
        model="fake-model",
        dataset_path=str(dataset_dir),
        prompt_style="fewshot",
        cache_dir=None,
    )
    client = OpenAICompatClient(base, timeout=10)
    run_eval(cfg, client=client)
    client.close()
    msgs = state.requests[0]["messages"]
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user", "assistant", "user"]
    assert msgs[1]["content"] == "ÖRNEK SORU"
    assert msgs[2]["content"] == "ÖRNEK CEVAP"


def test_prompt_style_bad_value(dataset_dir, fake_openai):
    from turkce_karne.errors import ClientError

    cfg = RunConfig(
        model="fake-model",
        dataset_path=str(dataset_dir),
        prompt_style="weird",
        cache_dir=None,
    )
    with pytest.raises(ClientError):
        run_eval(cfg)


def test_fingerprint_changes_with_prompt_style(dataset_dir):
    a = RunConfig(model="m", dataset_path=str(dataset_dir))
    b = RunConfig(
        model="m", dataset_path=str(dataset_dir), prompt_style="cot"
    )
    assert a.fingerprint() != b.fingerprint()


def test_html_shows_category_chart(dataset_dir, fake_openai, tmp_path):
    state, base = fake_openai
    state.add_rule("Bir sayı yaz", "42")
    state.add_rule("Cevap: 7", "Cevap: 7")
    r1 = _run(dataset_dir, base, state)
    state.default_content = "no"
    r2 = _run(dataset_dir, base, state)
    html = render_html([r1, r2])
    # two demo tasks in one category — chart only if ≥2 runs or ≥2 cats
    assert "<svg" in html and "<rect" in html


# ---- --repeat: real re-generations + rep-stability summary -----------------


def test_repeat_generates_independently(dataset_dir, fake_openai):
    state, base = fake_openai
    calls = {"n": 0}

    def responder(messages):
        calls["n"] += 1
        return "42"

    state.responder = responder
    results = _run(dataset_dir, base, state, repeat=3)
    assert calls["n"] == 2 * 3  # 2 tasks x 3 real generations, no cache reuse
    reps = sorted(t.get("rep", 0) for t in results["tasks"])
    assert reps == [0, 0, 1, 1, 2, 2]
    assert results["summary"]["n_rep_unstable"] == 0
    assert results["summary"]["rep_unstable"] == []


def test_repeat_detects_unstable_task(dataset_dir, fake_openai):
    state, base = fake_openai
    n = {"t1": 0}

    def responder(messages):
        user = next(m["content"] for m in messages if m["role"] == "user")
        if "Bir sayı" in user:
            n["t1"] += 1
            return "42" if n["t1"] == 1 else "no answer"
        return "Cevap: 7"

    state.responder = responder
    results = _run(dataset_dir, base, state, repeat=3)
    assert results["summary"]["n_rep_unstable"] == 1
    assert results["summary"]["rep_unstable"] == ["demo/t1"]
    t1_scores = [t["score"] for t in results["tasks"] if t["id"] == "demo/t1"]
    assert t1_scores == [1.0, 0.0, 0.0]


def test_repeat_scores_stay_sorted(dataset_dir, fake_openai):
    state, base = fake_openai
    state.add_rule("Bir sayı yaz", "42")
    state.add_rule("Cevap: 7", "Cevap: 7")
    results = _run(dataset_dir, base, state, repeat=2, concurrency=4)
    # scores are gathered by index — order must match selection order
    # regardless of completion interleaving
    assert [t["id"] for t in results["tasks"]] == [
        "demo/t1", "demo/t1", "demo/t2", "demo/t2"
    ]
    assert [t.get("rep", 0) for t in results["tasks"]] == [0, 1, 0, 1]
    assert results["summary"]["score"] == 1.0
    html = render_html(results)
    assert "@rep1" in html and "per task" in html


# ---- round 6: seeded bootstrap CI + rep rollups ----------------------------


def test_summary_ci95_present_and_deterministic(dataset_dir, fake_openai):
    state, base = fake_openai
    state.add_rule("Bir sayı yaz", "hiç")
    state.add_rule("Cevap: 7", "Cevap: 7")
    r1 = _run(dataset_dir, base, state)
    r2 = _run(dataset_dir, base, state)
    ci = r1["summary"]["ci95"]
    assert ci == r2["summary"]["ci95"]
    assert 0.0 <= ci[0] <= ci[1] <= 1.0


def test_repeat_rollups_bound_rep_variance(dataset_dir, fake_openai):
    state, base = fake_openai
    n = {"t1": 0}

    def responder(messages):
        user = next(m["content"] for m in messages if m["role"] == "user")
        if "Bir sayı" in user:
            n["t1"] += 1
            return "42" if n["t1"] == 1 else "no answer"
        return "Cevap: 7"

    state.responder = responder
    results = _run(dataset_dir, base, state, repeat=3)
    s = results["summary"]
    # t1 reps [1,0,0], t2 reps [1,1,1]: score = mean over all 6 rep scores
    # (per reps, by design); rollups bound per-task mean/worst/best spread
    assert s["score"] == pytest.approx(4 / 6, abs=1e-3)
    assert s["score_worst_rep"] == pytest.approx(0.5)
    assert s["score_best_rep"] == pytest.approx(1.0)
    html = render_html(results)
    assert "worst/best rep" in html and "95% CI" in html


def test_html_scorecard_structure(dataset_dir, fake_openai):
    state, base = fake_openai
    results = _run(dataset_dir, base, state)
    html = render_html(results)
    # structural invariants, not bytes: self-contained + required sections
    assert html.lstrip().lower().startswith("<!doctype html>")
    for anchor in ("Leaderboard", "Tasks", "Fingerprint", "Dataset"):
        assert anchor in html
    assert html.count("<details>") == 2
    # zero external assets: no remote script/link/img refs
    assert 'src="http' not in html and 'href="http' not in html
    assert "<svg" not in html  # 1 run x 1 category -> chart skipped


# ---- round 7: per-check-type stats ----------------------------------------


def test_summary_by_check_type(dataset_dir, fake_openai):
    state, base = fake_openai
    state.add_rule("Bir sayı yaz", "hiçbir şey")  # contains fails
    state.add_rule("Cevap: 7", "Cevap: 7")        # both checks pass
    results = _run(dataset_dir, base, state)
    bct = results["summary"]["by_check_type"]
    assert bct["contains"] == {"score": 0.0, "n": 1, "n_fail": 1}
    assert bct["answer_in"] == {"score": 1.0, "n": 1, "n_fail": 0}
    assert bct["count"] == {"score": 1.0, "n": 1, "n_fail": 0}
    # worst-first ordering
    assert list(bct) == ["contains", "answer_in", "count"] or list(bct)[:1] == ["contains"]


def test_html_check_type_table(dataset_dir, fake_openai):
    state, base = fake_openai
    state.add_rule("Bir sayı yaz", "hiçbir şey")
    state.add_rule("Cevap: 7", "Cevap: 7")
    html = render_html(_run(dataset_dir, base, state))
    assert "Check types" in html
    assert ">contains<" in html and "(1 fail)" in html


def test_html_check_type_matrix_multi_run():
    a = {
        "model": "A",
        "summary": {"score": 0.5},
        "tasks": [
            {"id": "c/1", "category": "c", "score": 1.0,
             "checks": [{"type": "contains", "passed": True}]},
        ],
    }
    b = {
        "model": "B",
        "summary": {"score": 1.0},
        "tasks": [
            {"id": "c/1", "category": "c", "score": 0.5,
             "checks": [{"type": "contains", "passed": False,
                         "fraction": 0.5}]},
        ],
    }
    html = render_html([a, b])
    assert "Check types" in html and ">contains<" in html
    # both run columns rendered (100% for A, 50% for B)
    assert "100.0%" in html and "50.0%" in html
    # sparse JSON fallback: same output computed from tasks, no crash
    assert "(1 fail)" in html


def test_markdown_check_type_table():
    r = {
        "model": "M",
        "summary": {"score": 0.5},
        "tasks": [
            {"id": "c/1", "category": "c", "score": 0.5,
             "checks": [{"type": "json_fields", "passed": False,
                         "fraction": 0.5}]},
        ],
    }
    md = render_markdown(r)
    assert "### Check types (worst first)" in md
    assert "| json_fields | 1 | 50.0% (1 fail) |" in md
