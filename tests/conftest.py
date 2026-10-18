"""Shared fixtures: a local fake OpenAI-compatible server.

Never touches the network — the fake runs on 127.0.0.1 in-process.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


class FakeOpenAIState:
    """Scripted-response state for the fake server."""

    def __init__(self):
        self.lock = threading.Lock()
        self.requests: list[dict] = []
        self.fail_next_n = 0
        self.fail_status = 429
        # substring -> canned content; first matching rule wins
        self.rules: list[tuple[str, str]] = []
        self.default_content = "tamam."
        # optional callable(messages) -> content; overrides rules when set.
        # Useful for stateful per-request variance (e.g. judge-runs).
        self.responder = None

    def add_rule(self, prompt_substr: str, content: str):
        self.rules.append((prompt_substr, content))

    def content_for(self, messages: list[dict]) -> str:
        if self.responder is not None:
            return self.responder(messages)
        user = next(
            (m["content"] for m in messages if m.get("role") == "user"), ""
        )
        for sub, content in self.rules:
            if sub in user:
                return content
        return self.default_content


def make_server(state: FakeOpenAIState) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, obj: dict):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode())
            except json.JSONDecodeError:
                return self._send(400, {"error": "bad json"})
            with state.lock:
                state.requests.append(payload)
                if state.fail_next_n > 0:
                    state.fail_next_n -= 1
                    return self._send(state.fail_status, {"error": "rate limited"})
            if self.path.rstrip("/") != "/v1/chat/completions":
                return self._send(404, {"error": "unknown path"})
            content = state.content_for(payload.get("messages", []))
            prompt_tokens = sum(
                len(m.get("content", "").split())
                for m in payload.get("messages", [])
            )
            self._send(
                200,
                {
                    "id": "chatcmpl-fake",
                    "object": "chat.completion",
                    "model": payload.get("model", "fake"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": content,
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": len(content.split()),
                        "total_tokens": prompt_tokens + len(content.split()),
                    },
                },
            )

        def log_message(self, *a):  # silence
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    return srv


@pytest.fixture()
def fake_openai():
    state = FakeOpenAIState()
    srv = make_server(state)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    base = f"http://127.0.0.1:{srv.server_port}/v1"
    try:
        yield state, base
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.fixture()
def dataset_dir(tmp_path):
    """A minimal two-task dataset for unit tests."""
    d = tmp_path / "dataset" / "v1"
    d.mkdir(parents=True)
    (d / "demo.yaml").write_text(
        """items:
  - id: demo/t1
    category: demo
    prompt: "Bir sayı yaz."
    checks:
      - type: contains
        terms: ["42"]
  - id: demo/t2
    category: demo
    prompt: "Son satırda 'Cevap: 7' yaz."
    checks:
      - type: answer_in
        answers: ["Cevap: 7"]
      - type: count
        unit: words
        min: 1
""",
        encoding="utf-8",
    )
    return tmp_path / "dataset"
