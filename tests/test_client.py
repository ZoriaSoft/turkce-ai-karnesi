"""Client behaviour against the fake server: success, retries, cache."""

import time

import pytest

from turkce_karne.client import (
    FileCache,
    GenerationConfig,
    OpenAICompatClient,
    cache_key,
    estimate_cost_usd,
)
from turkce_karne.errors import ClientError


def _msgs():
    return [{"role": "user", "content": "merhaba"}]


def test_success_and_usage(fake_openai):
    state, base = fake_openai
    state.add_rule("merhaba", "Merhaba! Size nasıl yardımcı olabilirim?")
    c = OpenAICompatClient(base, timeout=10)
    r = c.complete(GenerationConfig(model="fake"), _msgs())
    assert "Merhaba" in r.content
    assert not r.cached
    assert r.usage["prompt_tokens"] >= 1
    assert r.latency_ms >= 0
    c.close()
    assert len(state.requests) == 1


def test_retry_then_success(fake_openai):
    state, base = fake_openai
    state.fail_next_n = 2
    c = OpenAICompatClient(base, timeout=10, max_retries=3)
    # monkeypatch backoff to zero for speed
    c._sleep_backoff = lambda *a, **k: None
    r = c.complete(GenerationConfig(model="fake"), _msgs())
    assert r.content == state.default_content
    assert r.retries == 2
    assert len(state.requests) == 3
    c.close()


def test_fatal_4xx_no_retry(fake_openai):
    state, base = fake_openai
    state.fail_next_n = 5
    state.fail_status = 400
    c = OpenAICompatClient(base, timeout=10, max_retries=3)
    c._sleep_backoff = lambda *a, **k: None
    with pytest.raises(ClientError):
        c.complete(GenerationConfig(model="fake"), _msgs())
    assert len(state.requests) == 1  # no retry on 4xx
    c.close()


def test_exhausted_retries_raises(fake_openai):
    state, base = fake_openai
    state.fail_next_n = 10
    c = OpenAICompatClient(base, timeout=10, max_retries=2)
    c._sleep_backoff = lambda *a, **k: None
    with pytest.raises(ClientError):
        c.complete(GenerationConfig(model="fake"), _msgs())
    assert len(state.requests) == 3
    c.close()


def test_cache_hit(fake_openai, tmp_path):
    state, base = fake_openai
    cache = FileCache(tmp_path / "cache")
    c = OpenAICompatClient(base, timeout=10, cache=cache)
    gen = GenerationConfig(model="fake")
    r1 = c.complete(gen, _msgs())
    r2 = c.complete(gen, _msgs())
    assert r1.content == r2.content
    assert r2.cached
    assert len(state.requests) == 1
    c.close()


def test_cache_key_changes_with_params():
    m = _msgs()
    k1 = cache_key(GenerationConfig(model="a"), m)
    k2 = cache_key(GenerationConfig(model="b"), m)
    k3 = cache_key(GenerationConfig(model="a", temperature=0.5), m)
    assert len({k1, k2, k3}) == 3


def test_rpm_limiter_spacing(fake_openai):
    state, base = fake_openai
    c = OpenAICompatClient(base, timeout=10, rpm=120)  # 0.5s interval
    c._sleep_backoff = lambda *a, **k: None
    gen = GenerationConfig(model="fake")
    t0 = time.monotonic()
    c.complete(gen, _msgs())
    # vary messages to avoid cache
    c.complete(gen, [{"role": "user", "content": "ikinci"}])
    dt = time.monotonic() - t0
    assert dt >= 0.45
    c.close()


def test_cost_estimate_env(monkeypatch):
    monkeypatch.setenv("KARNE_PRICE_IN", "1.0")
    monkeypatch.setenv("KARNE_PRICE_OUT", "2.0")
    c = estimate_cost_usd(
        "whatever-model",
        {"prompt_tokens": 1_000_000, "completion_tokens": 500_000},
    )
    assert c == pytest.approx(2.0)


def test_content_parts_response(fake_openai):
    # OpenAI "content parts" shape should be flattened
    state, base = fake_openai
    c = OpenAICompatClient(base, timeout=10)
    joined = c._first_content(
        {
            "choices": [
                {"message": {"content": [{"type": "text", "text": "a"},
                                         {"type": "text", "text": "b"}]}}
            ]
        }
    )
    assert joined == "ab"
    c.close()
