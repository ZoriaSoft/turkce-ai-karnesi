"""Run the eval: tasks -> model -> deterministic checks -> results dict."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from . import __version__
from .checks import evaluate_check, task_score_value
from .client import (
    FileCache,
    GenerationConfig,
    OpenAICompatClient,
    estimate_cost_usd,
)
from .dataset import (
    categories,
    dataset_digest,
    items_digest,
    load_dataset,
    load_exemplars,
    resolve_dataset_dir,
)
from .errors import ClientError
from .judge import JudgeRunner
from .model import CheckResult, Task, TaskScore
from .stats import bootstrap_mean_ci

DEFAULT_SYSTEM = (
    "Sen yardımcı bir asistansın. Kullanıcının yönergesini aynen uygula; "
    "istenen biçime harfiyen uy."
)

# keys excluded from the reproducibility fingerprint (secrets/perf only)
_FP_EXCLUDE = {"api_key", "cache", "concurrency", "rpm", "timeout", "out", "label"}


@dataclass
class RunConfig:
    model: str
    base_url: str | None = None
    api_key: str | None = None
    dataset_path: str | None = None
    version: str = "v1"
    categories: list[str] | None = None
    task_ids: list[str] | None = None
    sample: int | None = None
    seed: int = 42
    repeat: int = 1
    temperature: float = 0.0
    max_tokens: int = 2048
    system_prompt: str = DEFAULT_SYSTEM
    concurrency: int = 4
    rpm: float | None = None
    cache_dir: str | None = None
    timeout: float = 60.0
    max_retries: int = 4
    label: str | None = None
    run_id: str | None = None
    # optional LLM judge (None = off). Judge uses its own endpoint/key
    # falling back to the main client's base_url/api_key.
    judge_model: str | None = None
    judge_base_url: str | None = None
    judge_api_key: str | None = None
    # blend: final = det*(1-w) + judge*w. 0 < w <= 1
    judge_weight: float = 0.4
    # categories the judge grades; None = judge.DEFAULT_JUDGE_CATEGORIES;
    # pass ["*"] to judge everything
    judge_categories: list[str] | None = None
    judge_max_tokens: int = 512
    # N independent judge attempts per response, merged into a
    # per-criterion median verdict (1 = single verdict)
    judge_runs: int = 1
    # prompt style: 'zero' (default), 'fewshot' (one exemplar per
    # category), 'cot' (chain-of-thought nudge suffix)
    prompt_style: str = "zero"

    def fingerprint(self) -> str:
        """sha256 over the config knobs that affect results (no secrets)."""
        d = {
            "model": self.model,
            "dataset_version": self.version,
            "categories": sorted(self.categories) if self.categories else None,
            "task_ids": sorted(self.task_ids) if self.task_ids else None,
            "sample": self.sample,
            "seed": self.seed,
            "repeat": self.repeat,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "system_prompt": self.system_prompt,
            "judge_model": self.judge_model,
            "judge_weight": self.judge_weight,
            "judge_categories": (
                sorted(self.judge_categories) if self.judge_categories else None
            ),
            "judge_runs": self.judge_runs,
            "prompt_style": self.prompt_style,
        }
        blob = json.dumps(d, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

def select_tasks(tasks: list[Task], cfg: RunConfig) -> list[tuple[Task, int]]:
    """Pick (task, repetition) pairs. ``rep`` is 0..cfg.repeat-1 and
    feeds a cache-key salt in :func:`_score_one` so every repetition is
    a real, independently sampled generation."""
    sel = list(tasks)
    if cfg.categories:
        want = set(cfg.categories)
        sel = [t for t in sel if t.category in want]
    if cfg.task_ids:
        want_ids = set(cfg.task_ids)
        sel = [t for t in sel if t.id in want_ids]
    sel.sort(key=lambda t: t.id)
    if cfg.sample and cfg.sample < len(sel):
        rng = random.Random(cfg.seed)
        sel = sorted(rng.sample(sel, cfg.sample), key=lambda t: t.id)
    return [(t, r) for t in sel for r in range(max(1, cfg.repeat))]


def _messages(
    task: Task,
    system: str,
    style: str = "zero",
    exemplar: dict | None = None,
) -> list[dict]:
    user = task.prompt if task.input is None else f"{task.prompt}\n\n{task.input}"
    if style == "cot":
        user = (
            user
            + "\n\nÖnce adım adım düşün, sonra nihai cevabını yaz."
        )
    msgs = [{"role": "system", "content": system}]
    if style == "fewshot" and exemplar:
        msgs.append({"role": "user", "content": exemplar["user"]})
        msgs.append({"role": "assistant", "content": exemplar["assistant"]})
    msgs.append({"role": "user", "content": user})
    return msgs


def _blend(det: float, judge_score: float | None, weight: float) -> float:
    if judge_score is None:
        return det
    return det * (1.0 - weight) + judge_score * weight


def _score_one(
    client: OpenAICompatClient,
    gen: GenerationConfig,
    task: Task,
    rep: int,
    system: str,
    judge: JudgeRunner | None = None,
    judge_weight: float = 0.4,
    style: str = "zero",
    exemplar: dict | None = None,
) -> TaskScore:
    # rep 0 reuses the plain cache entry; later reps get a salt so the
    # model is actually re-asked instead of served the same cached text
    if rep:
        gen = dataclasses.replace(gen, cache_salt=f"rep-{rep}")
    try:
        res = client.complete(gen, _messages(task, system, style, exemplar))
    except ClientError as e:
        return TaskScore(
            id=task.id, category=task.category, score=0.0, error=str(e),
            rep=rep,
        )
    content = res.content
    if content is None:
        return TaskScore(
            id=task.id,
            category=task.category,
            score=0.0,
            error="empty_response",
            cached=res.cached,
            latency_ms=res.latency_ms,
            retries=res.retries,
            usage=res.usage,
            rep=rep,
        )
    try:
        results: list[CheckResult] = [
            evaluate_check(c, content, task) for c in task.checks
        ]
    except Exception as e:  # dataset spec bug surfaced at run time
        return TaskScore(
            id=task.id,
            category=task.category,
            score=0.0,
            response=content,
            error=f"check_error: {e}",
            cached=res.cached,
            latency_ms=res.latency_ms,
            retries=res.retries,
            usage=res.usage,
            rep=rep,
        )
    det = task_score_value(results)
    jres = (
        judge.judge(task, content)
        if judge is not None and judge.applies(task.category)
        else None
    )
    score = det if jres is None else _blend(det, jres.score, judge_weight)
    return TaskScore(
        id=task.id,
        category=task.category,
        score=score,
        response=content,
        checks=results,
        cached=res.cached,
        latency_ms=res.latency_ms,
        retries=res.retries,
        usage=res.usage,
        det_score=det,
        judge=jres.to_dict() if jres is not None else None,
        rep=rep,
    )


def run_eval(
    cfg: RunConfig,
    client: OpenAICompatClient | None = None,
    judge_client: OpenAICompatClient | None = None,
) -> dict:
    """Execute the run and return the serializable results dict."""
    base = resolve_dataset_dir(cfg.dataset_path)
    tasks = load_dataset(base, version=cfg.version)
    selected = select_tasks(tasks, cfg)
    if not selected:
        raise ClientError("no tasks selected (check --tasks/--categories/--sample)")

    cache = FileCache(cfg.cache_dir)
    if cfg.prompt_style not in ("zero", "fewshot", "cot"):
        raise ClientError(
            f"unknown prompt_style {cfg.prompt_style!r} (zero|fewshot|cot)"
        )
    exemplars = (
        load_exemplars(cfg.dataset_path, version=cfg.version)
        if cfg.prompt_style == "fewshot"
        else {}
    )
    gen = GenerationConfig(
        model=cfg.model,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
    )
    own_client = client is None
    if own_client:
        from .client import client_from_env

        client = client_from_env(
            base_url=cfg.base_url,
            api_key=cfg.api_key,
            rpm=cfg.rpm,
            timeout=cfg.timeout,
            max_retries=cfg.max_retries,
            cache=cache,
        )
    else:
        client.cache = cache

    judge: JudgeRunner | None = None
    own_judge_client = False
    if cfg.judge_model:
        if not 0 < cfg.judge_weight <= 1:
            raise ClientError("judge_weight must be in (0, 1]")
        if cfg.judge_runs < 1 or cfg.judge_runs > 9:
            raise ClientError("judge_runs must be in 1..9")
        if judge_client is None:
            from .client import client_from_env

            # judge endpoint/key: explicit judge args > KARNE_JUDGE_* env >
            # main client's credentials
            j_base = (
                cfg.judge_base_url
                or os.environ.get("KARNE_JUDGE_BASE_URL")
                or client.base_url
            )
            j_key = (
                cfg.judge_api_key
                if cfg.judge_api_key is not None
                else os.environ.get("KARNE_JUDGE_API_KEY", client.api_key)
            )
            judge_client = client_from_env(
                base_url=j_base,
                api_key=j_key,
                rpm=cfg.rpm,
                timeout=cfg.timeout,
                max_retries=cfg.max_retries,
                cache=cache,
            )
            own_judge_client = True
        else:
            judge_client.cache = cache
        cats = (
            None
            if cfg.judge_categories is None
            else set(cfg.judge_categories)
        )
        judge = JudgeRunner(
            judge_client,
            cfg.judge_model,
            categories=cats,
            max_tokens=cfg.judge_max_tokens,
            runs=cfg.judge_runs,
        )

    started = time.time()
    scores: list[TaskScore] = []
    if cfg.concurrency > 1 and len(selected) > 1:
        with ThreadPoolExecutor(max_workers=cfg.concurrency) as pool:
            futs = {
                pool.submit(
                    _score_one,
                    client,
                    gen,
                    t,
                    rep,
                    cfg.system_prompt,
                    judge,
                    cfg.judge_weight,
                    cfg.prompt_style,
                    exemplars.get(t.category) or exemplars.get("default"),
                ): i
                for i, (t, rep) in enumerate(selected)
            }
            tmp: dict[int, TaskScore] = {}
            for fut in as_completed(futs):
                tmp[futs[fut]] = fut.result()
            scores = [tmp[i] for i in range(len(selected))]
    else:
        scores = [
            _score_one(
                client,
                gen,
                t,
                rep,
                cfg.system_prompt,
                judge,
                cfg.judge_weight,
                cfg.prompt_style,
                exemplars.get(t.category) or exemplars.get("default"),
            )
            for t, rep in selected
        ]
    elapsed_ms = int((time.time() - started) * 1000)
    if own_client:
        client.close()
    if own_judge_client:
        judge_client.close()
    per_task = [s.to_dict() for s in scores]
    task_scores: dict[str, list[float]] = {}
    for s in scores:
        task_scores.setdefault(s.id, []).append(s.score)
    # tasks whose pass/fail verdict flips between repetitions — a cheap
    # signal for model nondeterminism when --repeat > 1
    rep_unstable: list[str] = []
    if cfg.repeat > 1:
        rep_unstable = sorted(
            tid
            for tid, v in task_scores.items()
            if len({x >= 0.999 for x in v}) > 1
        )
    # cluster bootstrap: reps of one task stay together, so the interval
    # reflects task-level uncertainty, not sampling noise inside reps
    ci = bootstrap_mean_ci(
        [task_scores[k] for k in sorted(task_scores)], tag="score"
    )
    n = len(scores)
    mean = sum(s.score for s in scores) / n if n else 0.0
    cat_sums: dict[str, list[float]] = {}
    for s in scores:
        cat_sums.setdefault(s.category, []).append(s.score)
    by_cat = {
        c: {"score": round(sum(v) / len(v), 4), "n": len(v)}
        for c, v in sorted(cat_sums.items())
    }
    tokens_in = sum(
        (s.usage or {}).get("prompt_tokens", 0)
        + (s.usage or {}).get("input_tokens", 0)
        for s in scores
    )
    tokens_out = sum(
        (s.usage or {}).get("completion_tokens", 0)
        + (s.usage or {}).get("output_tokens", 0)
        for s in scores
    )
    cost = estimate_cost_usd(
        cfg.model, {"prompt_tokens": tokens_in, "completion_tokens": tokens_out}
    )
    judged = [s for s in scores if s.judge is not None]
    j_ok = [s for s in judged if (s.judge or {}).get("score") is not None]
    j_tokens_in = sum(
        (s.judge.get("usage") or {}).get("prompt_tokens", 0)
        + (s.judge.get("usage") or {}).get("input_tokens", 0)
        for s in judged
    )
    j_tokens_out = sum(
        (s.judge.get("usage") or {}).get("completion_tokens", 0)
        + (s.judge.get("usage") or {}).get("output_tokens", 0)
        for s in judged
    )
    j_cost = (
        estimate_cost_usd(
            cfg.judge_model,
            {"prompt_tokens": j_tokens_in, "completion_tokens": j_tokens_out},
        )
        if cfg.judge_model
        else None
    )
    results = {
        "format": "turkce-karne/v1",
        "tool_version": __version__,
        "run_id": cfg.run_id
        or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "label": cfg.label,
        "model": cfg.model,
        "dataset": {
            "version": cfg.version,
            "sha256": dataset_digest(base, version=cfg.version),
            "items_sha256": items_digest(tasks),
            "n_items_total": len(tasks),
            "n_run": n,
            "categories": categories(tasks),
        },
        "config_fingerprint": cfg.fingerprint(),
        "config": {
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "seed": cfg.seed,
            "sample": cfg.sample,
            "repeat": cfg.repeat,
            "categories": cfg.categories,
            "task_ids": cfg.task_ids,
            "prompt_style": cfg.prompt_style,
        },
        "summary": {
            "score": round(mean, 4),
            "ci95": [round(ci[0], 4), round(ci[1], 4)] if ci else None,
            "n": n,
            "errors": sum(1 for s in scores if s.error),
            "by_category": by_cat,
            "elapsed_ms": elapsed_ms,
            "tokens_in": tokens_in or None,
            "tokens_out": tokens_out or None,
            "est_cost_usd": round(cost, 6) if cost is not None else None,
            "cache_hits": sum(1 for s in scores if s.cached),
        },
        "tasks": per_task,
    }
    if cfg.repeat > 1:
        results["summary"]["n_rep_unstable"] = len(rep_unstable)
        results["summary"]["rep_unstable"] = rep_unstable
        # best/worst-rep rollups bound how much of the mean is sampling luck
        results["summary"]["score_worst_rep"] = round(
            sum(min(v) for v in task_scores.values())
            / len(task_scores),
            4,
        )
        results["summary"]["score_best_rep"] = round(
            sum(max(v) for v in task_scores.values())
            / len(task_scores),
            4,
        )
    if judge is not None:
        results["judge"] = {
            "model": cfg.judge_model,
            "weight": cfg.judge_weight,
            "runs": cfg.judge_runs,
            "n_judged": len(j_ok),
            "n_judge_errors": len(judged) - len(j_ok),
            "est_cost_usd": (
                round(j_cost, 6) if j_cost is not None else None
            ),
        }
    return results


def save_results(results: dict, out_path) -> None:
    from pathlib import Path

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, sort_keys=False)
        + "\n",
        encoding="utf-8",
    )


def load_results(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def merge_runs(runs: Iterable[dict]) -> list[dict]:
    """Sort multi-run records for the compare/report view."""
    return sorted(runs, key=lambda r: r.get("summary", {}).get("score", 0), reverse=True)
