"""OpenAI-compatible chat-completions client.

Features: JSON file cache (content-addressed keys), exponential backoff with
jitter on 429/5xx/timeouts, requests-per-minute pacing, token-usage capture.
All behaviour is deterministic given the same request fingerprint.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .errors import ClientError
from .model import CompletionResult

_RETRY_STATUS = {429, 500, 502, 503, 504, 529}


@dataclass
class GenerationConfig:
    model: str
    temperature: float = 0.0
    max_tokens: int = 2048
    extra: dict = field(default_factory=dict)
    # cache-only discriminator: joins the cache key but is NEVER sent
    # on the wire. Used to force N independent judge verdicts for one
    # identical payload (--judge-runs).
    cache_salt: str | None = None

    def payload(self, messages: list[dict]) -> dict:
        p: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        p.update(self.extra)
        return p


def cache_key(gen: GenerationConfig, messages: list[dict]) -> str:
    blob = json.dumps(
        gen.payload(messages), ensure_ascii=False, sort_keys=True
    )
    if gen.cache_salt:
        blob += f"\x00salt:{gen.cache_salt}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class FileCache:
    """Flat JSON cache: one file per request fingerprint."""

    def __init__(self, path: str | Path | None):
        self.enabled = path is not None and str(path).lower() not in ("", "off", "none")
        self.dir = Path(path) if self.enabled else None
        if self.enabled:
            self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _file(self, key: str) -> Path:
        assert self.dir is not None
        return self.dir / f"{key}.json"

    def get(self, key: str) -> dict | None:
        if not self.enabled:
            return None
        f = self._file(key)
        if not f.exists():
            return None
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def put(self, key: str, record: dict) -> None:
        if not self.enabled:
            return
        f = self._file(key)
        # unique tmp name: two threads writing the same key must not
        # interleave into one temp file
        tmp = f.with_name(f"{f.stem}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(
            json.dumps(record, ensure_ascii=False, indent=None), encoding="utf-8"
        )
        with self._lock:
            tmp.replace(f)


class RateLimiter:
    """Simple global pacer: enforces a minimum spacing between requests."""

    def __init__(self, rpm: float | None):
        self.min_interval = 60.0 / rpm if rpm and rpm > 0 else 0.0
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            if now < self._next:
                time.sleep(self._next - now)
                now = time.monotonic()
            self._next = now + self.min_interval


class OpenAICompatClient:
    """Minimal chat-completions client for any OpenAI-compatible endpoint."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        timeout: float = 60.0,
        max_retries: int = 4,
        rpm: float | None = None,
        cache: FileCache | None = None,
    ):
        if not base_url or not base_url.startswith(("http://", "https://")):
            raise ClientError(f"invalid base_url: {base_url!r}")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self._http = httpx.Client(timeout=timeout)
        self._limiter = RateLimiter(rpm)
        self.cache = cache or FileCache(None)
        self._rng = random.Random(20261018)

    # -- public ---------------------------------------------------------

    def complete(
        self, gen: GenerationConfig, messages: list[dict]
    ) -> CompletionResult:
        key = cache_key(gen, messages)
        cached = self.cache.get(key)
        if cached is not None:
            return CompletionResult(
                content=cached.get("content"),
                cached=True,
                latency_ms=0,
                usage=cached.get("usage"),
                retries=0,
            )
        record = self._request_with_retries(gen.payload(messages))
        # an empty/None completion is usually transient (filtered or
        # truncated output); caching it would pin the failure forever
        if record.get("content"):
            self.cache.put(key, record)
        return CompletionResult(
            content=record.get("content"),
            cached=False,
            latency_ms=record.get("latency_ms", 0),
            usage=record.get("usage"),
            retries=record.get("retries", 0),
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- internals -------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _request_with_retries(self, payload: dict) -> dict:
        url = f"{self.base_url}/chat/completions"
        last_err: str | None = None
        for attempt in range(self.max_retries + 1):
            self._limiter.wait()
            started = time.perf_counter()
            try:
                r = self._http.post(
                    url, json=payload, headers=self._headers()
                )
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_err = f"{type(e).__name__}: {e}"
                if attempt < self.max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise ClientError(f"request failed: {last_err}") from e
            latency_ms = int((time.perf_counter() - started) * 1000)
            if r.status_code == 200:
                try:
                    data = r.json()
                except json.JSONDecodeError as e:
                    raise ClientError(
                        f"non-JSON 200 response from {url}"
                    ) from e
                return {
                    "content": self._first_content(data),
                    "usage": data.get("usage"),
                    "latency_ms": latency_ms,
                    "retries": attempt,
                    "status": 200,
                }
            body = r.text[:500]
            if r.status_code in _RETRY_STATUS and attempt < self.max_retries:
                self._sleep_backoff(attempt, r)
                last_err = f"HTTP {r.status_code}: {body}"
                continue
            raise ClientError(f"HTTP {r.status_code}: {body}")
        raise ClientError(f"request failed after retries: {last_err}")

    def _sleep_backoff(self, attempt: int, resp: httpx.Response | None = None):
        ra = None
        if resp is not None:
            ra = resp.headers.get("Retry-After")
        if ra is not None:
            try:
                delay = min(float(ra), 60.0)
            except ValueError:
                delay = 0.0
        else:
            delay = 0.0
        if delay <= 0:
            delay = min(2.0**attempt * 0.5, 30.0)
        delay += self._rng.uniform(0.0, 0.25)
        time.sleep(delay)

    @staticmethod
    def _first_content(data: dict) -> str | None:
        try:
            choices = data.get("choices") or []
            if not choices:
                return None
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if isinstance(content, list):  # content parts
                return "".join(
                    p.get("text", "") for p in content if isinstance(p, dict)
                )
            return content
        except (AttributeError, IndexError, KeyError):
            return None


def client_from_env(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
    rpm: float | None = None,
    max_retries: int = 4,
    cache: FileCache | None = None,
) -> OpenAICompatClient:
    """Build a client from env vars, overridable by explicit args."""
    bu = base_url or os.environ.get("KARNE_BASE_URL")
    key = api_key if api_key is not None else os.environ.get("KARNE_API_KEY")
    if not bu:
        raise ClientError(
            "no base_url: pass --base-url or set KARNE_BASE_URL"
        )
    to = timeout
    if to is None:
        env_to = os.environ.get("KARNE_TIMEOUT")
        to = float(env_to) if env_to else 60.0
    if rpm is None:
        env_rpm = os.environ.get("KARNE_RPM")
        rpm = float(env_rpm) if env_rpm else None
    return OpenAICompatClient(
        bu,
        key,
        timeout=to,
        max_retries=max_retries,
        rpm=rpm,
        cache=cache,
    )


# minimal public price table (USD per 1M tokens) — extend as needed
_PRICE_TABLE: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.0),
    "gpt-5-mini": (0.25, 2.00),
    "deepseek-chat": (0.27, 1.10),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "qwen2.5-72b": (0.36, 0.40),
}


def estimate_cost_usd(model: str, usage: dict | None) -> float | None:
    """Cost estimate from env override or the built-in table."""
    if not usage:
        return None
    pin = os.environ.get("KARNE_PRICE_IN")
    pout = os.environ.get("KARNE_PRICE_OUT")
    if pin is not None and pout is not None:
        price_in, price_out = float(pin), float(pout)
    else:
        found = None
        for k, v in _PRICE_TABLE.items():
            if k in model:
                found = v
                break
        if found is None:
            return None
        price_in, price_out = found
    ti = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    to = usage.get("completion_tokens") or usage.get("output_tokens") or 0
    return (ti * price_in + to * price_out) / 1_000_000
