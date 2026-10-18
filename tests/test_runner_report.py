"""End-to-end runner and report tests using the fake server."""

import json

import pytest

from turkce_karne.client import OpenAICompatClient
from turkce_karne.report import render_html, write_html
from turkce_karne.runner import RunConfig, load_results, run_eval, save_results


def _run(dataset_dir, base, state, **kw):
    cfg = RunConfig(
        model="fake-model",
        dataset_path=str(dataset_dir),
        concurrency=1,
        cache_dir=None,
        **kw,
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
