"""LLM judge tests: parsing, blending, and end-to-end via fake server."""

import pytest  # noqa: I001

from turkce_karne.client import OpenAICompatClient
from turkce_karne.judge import (
    CRITERIA,
    DEFAULT_JUDGE_CATEGORIES,
    JudgeRunner,
    judge_messages,
    parse_judge_json,
)
from turkce_karne.model import Task
from turkce_karne.runner import RunConfig, run_eval


# ---- parse_judge_json -----------------------------------------------------


def test_parse_valid_json():
    scores, rationale, err = parse_judge_json(
        '{"instruction_following": 3, "turkish_quality": 2,'
        ' "correctness": 3, "rationale": "iyi"}'
    )
    assert err is None
    assert scores == {
        "instruction_following": 3,
        "turkish_quality": 2,
        "correctness": 3,
    }
    assert rationale == "iyi"


def test_parse_json_embedded_in_text():
    scores, _, err = parse_judge_json(
        'Sure, here is my verdict: {"instruction_following": 1,'
        ' "turkish_quality": 0, "correctness": 2} thanks'
    )
    assert err is None and scores["turkish_quality"] == 0


def test_parse_rejects_missing_criterion():
    scores, _, err = parse_judge_json('{"instruction_following": 3}')
    assert scores is None and "missing_or_bad_criteria" in err


def test_parse_rejects_out_of_range():
    scores, _, err = parse_judge_json(
        '{"instruction_following": 4, "turkish_quality": 3,'
        ' "correctness": 3}'
    )
    assert scores is None and "instruction_following" in err


def test_parse_rejects_bool_and_float():
    scores, _, err = parse_judge_json(
        '{"instruction_following": true, "turkish_quality": 2.5,'
        ' "correctness": 3}'
    )
    assert scores is None and err


def test_parse_string_digits_coerced():
    scores, _, err = parse_judge_json(
        '{"instruction_following": "3", "turkish_quality": "2",'
        ' "correctness": "1"}'
    )
    assert err is None and scores["correctness"] == 1


def test_parse_empty_and_garbage():
    assert parse_judge_json("")[2] == "empty_judge_response"
    assert parse_judge_json("no json here")[2] == "no_json"


def test_criteria_all_capped_at_3():
    assert set(CRITERIA.values()) == {3}


# ---- judge_messages --------------------------------------------------------


def test_judge_messages_contain_task_and_response():
    t = Task(id="demo/x", category="demo", prompt="Bir dilekçe yaz.")
    msgs = judge_messages(t, "model cevabı")
    assert msgs[0]["role"] == "system"
    assert "Bir dilekçe yaz." in msgs[1]["content"]
    assert "model cevabı" in msgs[1]["content"]


def test_judge_messages_truncates_long_response():
    t = Task(id="demo/x", category="demo", prompt="p")
    msgs = judge_messages(t, "x" * 9000)
    assert len(msgs[1]["content"]) < 9000
    assert "kısaltıldı" in msgs[1]["content"]


# ---- JudgeRunner via fake server ------------------------------------------


def _jclient(base, state):
    return OpenAICompatClient(base, api_key="k", timeout=5, max_retries=0)


def test_judge_runner_scoring(fake_openai):
    state, base = fake_openai
    state.add_rule(
        "MODEL ÇIKTISI",
        '{"instruction_following": 3, "turkish_quality": 3,'
        ' "correctness": 0, "rationale": "yanlış cevap"}',
    )
    jr = JudgeRunner(_jclient(base, state), "judge-x", categories={"demo"})
    t = Task(id="demo/t", category="demo", prompt="p")
    res = jr.judge(t, "resp")
    assert res.error is None
    assert res.score == pytest.approx(6 / 9)
    assert res.scores["correctness"] == 0
    assert res.rationale == "yanlış cevap"


def test_judge_runner_parse_failure_has_error(fake_openai):
    state, base = fake_openai
    state.add_rule("MODEL ÇIKTISI", "not json")
    jr = JudgeRunner(_jclient(base, state), "judge-x", categories={"demo"})
    res = jr.judge(Task(id="d/t", category="demo", prompt="p"), "r")
    assert res.score is None and "judge_parse" in res.error


def test_judge_runner_categories():
    jr = JudgeRunner.__new__(JudgeRunner)
    jr.categories = set(DEFAULT_JUDGE_CATEGORIES)
    jr.judge_all = False
    assert jr.applies("resmi-yazi") and not jr.applies("imla")
    jr2 = JudgeRunner.__new__(JudgeRunner)
    jr2.categories, jr2.judge_all = set(), True
    assert jr2.applies("anything")


# ---- end-to-end blend through run_eval ------------------------------------


def _run_cfg(dataset_dir, **kw):
    base_kw = {
        "model": "fake-model",
        "dataset_path": str(dataset_dir),
        "temperature": 0.0,
        "concurrency": 1,
        "cache_dir": None,
    }
    base_kw.update(kw)
    return RunConfig(**base_kw)


def test_run_eval_judge_blend(dataset_dir, fake_openai):
    state, base = fake_openai
    # judge rule first: the judge prompt embeds the task prompt, so the
    # task rule would otherwise match judge requests too
    state.add_rule(
        "MODEL ÇIKTISI",
        '{"instruction_following": 0, "turkish_quality": 0,'
        ' "correctness": 0}',
    )
    state.add_rule("Bir sayı yaz.", "42")
    client = OpenAICompatClient(base, api_key="k", timeout=5, max_retries=0)
    judge_client = OpenAICompatClient(base, api_key="k", timeout=5, max_retries=0)
    cfg = _run_cfg(
        dataset_dir,
        judge_model="judge-fake",
        judge_weight=0.4,
        judge_categories=["*"],
    )
    results = run_eval(cfg, client=client, judge_client=judge_client)
    t1 = next(t for t in results["tasks"] if t["id"] == "demo/t1")
    # det=1.0 (contains "42"), judge=0.0 -> blended 0.6
    assert t1["det_score"] == 1.0
    assert t1["judge"]["score"] == 0.0
    assert t1["score"] == pytest.approx(0.6)
    assert results["judge"]["model"] == "judge-fake"
    assert results["judge"]["n_judged"] == 2
    client.close()
    judge_client.close()


def test_run_eval_judge_skips_other_categories(dataset_dir, fake_openai):
    state, base = fake_openai
    state.add_rule("Bir sayı yaz.", "42")
    state.add_rule("Cevap: 7", "Cevap: 7")
    client = OpenAICompatClient(base, api_key="k", timeout=5, max_retries=0)
    judge_client = OpenAICompatClient(base, api_key="k", timeout=5, max_retries=0)
    cfg = _run_cfg(
        dataset_dir,
        judge_model="judge-fake",
        judge_categories=["ozet"],  # no 'demo' -> judge never fires
    )
    results = run_eval(cfg, client=client, judge_client=judge_client)
    assert results["judge"]["n_judged"] == 0
    assert all(t.get("judge") is None for t in results["tasks"])
    client.close()
    judge_client.close()


def test_run_eval_judge_error_falls_back_to_det(dataset_dir, fake_openai):
    state, base = fake_openai
    state.add_rule("MODEL ÇIKTISI", "broken verdict, no json")
    state.add_rule("Bir sayı yaz.", "42")
    client = OpenAICompatClient(base, api_key="k", timeout=5, max_retries=0)
    judge_client = OpenAICompatClient(base, api_key="k", timeout=5, max_retries=0)
    cfg = _run_cfg(
        dataset_dir,
        judge_model="judge-fake",
        judge_categories=["*"],
    )
    results = run_eval(cfg, client=client, judge_client=judge_client)
    t1 = next(t for t in results["tasks"] if t["id"] == "demo/t1")
    assert t1["judge"]["error"].startswith("judge_parse")
    assert t1["score"] == t1["det_score"]  # fallback
    assert results["judge"]["n_judge_errors"] == 2
    client.close()
    judge_client.close()


def test_fingerprint_changes_with_judge(dataset_dir):
    a = _run_cfg(dataset_dir)
    b = _run_cfg(dataset_dir, judge_model="j")
    c = _run_cfg(dataset_dir, judge_model="j", judge_weight=0.2)
    assert a.fingerprint() != b.fingerprint() != c.fingerprint()
