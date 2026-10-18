"""Dataclasses shared across dataset, checks, runner and report."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Task:
    id: str
    category: str
    prompt: str
    input: str | None = None
    expected: Any = None
    checks: list[dict] = field(default_factory=list)
    difficulty: int = 1
    notes: str | None = None


@dataclass
class CheckResult:
    type: str
    passed: bool
    # optional partial credit for a FAILING check (e.g. 4/5 JSON fields);
    # None means binary pass/fail
    fraction: float | None = None
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {"type": self.type, "passed": self.passed}
        if self.fraction is not None:
            d["fraction"] = round(self.fraction, 4)
        if self.detail:
            d["detail"] = self.detail
        return d


@dataclass
class CompletionResult:
    content: str | None = None
    cached: bool = False
    latency_ms: int = 0
    usage: dict | None = None
    retries: int = 0

    def to_dict(self) -> dict:
        d = {
            "cached": self.cached,
            "latency_ms": self.latency_ms,
            "retries": self.retries,
        }
        if self.usage:
            d["usage"] = self.usage
        return d


@dataclass
class TaskScore:
    id: str
    category: str
    score: float
    response: str | None = None
    error: str | None = None
    checks: list[CheckResult] = field(default_factory=list)
    cached: bool = False
    latency_ms: int = 0
    retries: int = 0
    usage: dict | None = None
    # deterministic-only score before judge blending; equals ``score``
    # when no judge ran for this task
    det_score: float | None = None
    # serializable judge verdict dict (JudgeResult.to_dict) or None
    judge: dict | None = None
    # repetition index when --repeat > 1 (0 = first pass); each rep gets
    # a distinct cache key so every pass is a real generation
    rep: int = 0
    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "category": self.category,
            "score": round(self.score, 4),
            "checks": [c.to_dict() for c in self.checks],
            "latency_ms": self.latency_ms,
        }
        if self.det_score is not None:
            d["det_score"] = round(self.det_score, 4)
        if self.judge is not None:
            d["judge"] = self.judge
        if self.response is not None:
            d["response"] = self.response
        if self.error is not None:
            d["error"] = self.error
        if self.cached:
            d["cached"] = True
        if self.retries:
            d["retries"] = self.retries
        if self.rep:
            d["rep"] = self.rep
        if self.usage:
            d["usage"] = self.usage
        return d
