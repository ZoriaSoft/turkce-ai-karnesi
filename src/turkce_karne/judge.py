"""Optional LLM judge with a fixed rubric.

The judge is a second model call (its own endpoint/model/key) that grades
the evaluated model's response on three fixed criteria, each 0-3:

- ``instruction_following`` — does the response follow the stated
  instructions and required format?
- ``turkish_quality`` — Turkish grammar, spelling (de/da, ki, mi,
  dotted-i), and naturalness.
- ``correctness`` — is the content actually right for the task?

Contract: the judge must answer with strict JSON only
(``{"instruction_following": 0-3, "turkish_quality": 0-3,
"correctness": 0-3, "rationale": "<short tr>"}``). Parse or range
failures produce ``score=None`` plus an error so the caller can fall back
to the deterministic score. Judge calls reuse the same
:class:`~turkce_karne.client.OpenAICompatClient` machinery, so caching,
retries, and rate limits apply; the cache key includes the judge model
and the graded response text.

``runs`` > 1 (``--judge-runs``) issues N independent attempts with
distinct cache keys and merges them into a per-criterion median verdict,
mitigating single-verdict variance.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .checks import extract_json
from .client import GenerationConfig, OpenAICompatClient
from .errors import ClientError
from .model import Task

# fixed rubric: criterion key -> max points
CRITERIA: dict[str, int] = {
    "instruction_following": 3,
    "turkish_quality": 3,
    "correctness": 3,
}

# categories where deterministic checks cannot see quality; judge adds
# the missing signal by default. All others stay check-only unless
# --judge-categories widens the set (use "all").
DEFAULT_JUDGE_CATEGORIES = ("resmi-yazi", "eposta", "ozet", "ceviri")

_JUDGE_SYSTEM = (
    "Sen Türkçe değerlendirme jürissin. Verilen görev çıktısını rubriğe "
    "göre puanla ve YALNIZCA geçerli JSON döndür. Açıklama, markdown veya "
    "kod bloğu ekleme."
)

_JUDGE_RUBRIC = """\
Aşağıdaki model çıktısını üç ölçüte göre puanla. Her ölçüt 0-3 arası
tam sayı:

- instruction_following: İstenen biçim ve kurallara uyum (satır sayısı,
  önek, "yalnızca JSON" gibi kısıtlar, istenen dil).
- turkish_quality: Türkçe dilbilgisi, imla (de/da, ki, mi ayrı yazımı,
  İ/ı doğru kullanımı), doğal ve akıcı anlatım.
- correctness: İçeriğin görev açısından doğruluğu (doğru bilgi, doğru
  alanlar, anlamın korunması).

Puanlama: 3 = kusursuz/ihmal edilebilir hata, 2 = küçük hata(lar),
1 = belirgin hata(lar) ama kısmen doğru, 0 = yanlış, eksik veya kuralsız.

YALNIZCA şu JSON şemasıyla cevap ver:
{"instruction_following": N, "turkish_quality": N, "correctness": N,
 "rationale": "tek cümlelik Türkçe gerekçe"}
"""

MAX_RESPONSE_CHARS = 4000  # bound judge prompt size


def judge_messages(task: Task, response: str) -> list[dict]:
    user_text = task.prompt + (f"\n\n{task.input}" if task.input else "")
    resp = response[:MAX_RESPONSE_CHARS]
    if len(response) > MAX_RESPONSE_CHARS:
        resp += "\n[... kısaltıldı ...]"
    user = (
        f"GÖREV:\n{user_text}\n\n"
        f"MODEL ÇIKTISI:\n{resp}\n\n"
        f"{_JUDGE_RUBRIC}"
    )
    return [
        {"role": "system", "content": _JUDGE_SYSTEM},
        {"role": "user", "content": user},
    ]


@dataclass
class JudgeResult:
    """One judge verdict. ``score`` is normalized to 0..1; ``None``
    means the judge call failed or returned unusable JSON. With
    ``judge_runs > 1`` this is a per-criterion median over independent
    attempts (each cached under its own salt)."""

    score: float | None = None
    error: str | None = None
    scores: dict = field(default_factory=dict)
    rationale: str | None = None
    raw: str | None = None
    cached: bool = False
    latency_ms: int = 0
    usage: dict | None = None
    # per-attempt detail, populated only when judge_runs > 1:
    # [{"score": <raw point total or null>, "error": <str or null>}, ...]
    runs: list[dict] | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "score": round(self.score, 4) if self.score is not None else None,
        }
        if self.scores:
            d["scores"] = self.scores
        if self.rationale:
            d["rationale"] = self.rationale
        if self.error:
            d["error"] = self.error
        if self.cached:
            d["cached"] = True
        if self.usage:
            d["usage"] = self.usage
        if self.runs is not None:
            d["runs"] = self.runs
            d["n_errors"] = sum(1 for r in self.runs if r.get("score") is None)
        return d


def parse_judge_json(text: str | None) -> tuple[dict | None, str | None, str | None]:
    """Extract (scores, rationale, error) from judge output text."""
    if not text or not text.strip():
        return None, None, "empty_judge_response"
    data = extract_json(text)
    if not isinstance(data, dict):
        return None, None, "no_json"
    scores: dict[str, int] = {}
    missing = []
    for key, cap in CRITERIA.items():
        v = data.get(key)
        if isinstance(v, str) and v.isdigit():
            v = int(v)
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= cap:
            missing.append(key)
            continue
        scores[key] = v
    if missing:
        return None, None, f"missing_or_bad_criteria: {','.join(missing)}"
    rationale = data.get("rationale")
    return scores, (str(rationale)[:300] if rationale is not None else None), None


def _median(xs: list[float]) -> float:
    """Median: middle value, or mean of the two middle values."""
    s = sorted(xs)
    m = len(s) // 2
    if len(s) % 2:
        return float(s[m])
    return (s[m - 1] + s[m]) / 2.0


def _sum_usage(usages: list[dict | None]) -> dict | None:
    """Sum numeric usage fields over attempts; None when nothing seen."""
    if not any(usages):
        return None
    total: dict[str, float] = {}
    for u in usages:
        for k, v in (u or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                total[k] = total.get(k, 0) + v
    return total or None


def _merge_verdicts(verdicts: list[JudgeResult]) -> JudgeResult:
    """Merge N judge attempts into one verdict.

    Successful attempts contribute their criterion scores; the merged
    verdict is the per-criterion median (odd count → middle value, even
    count → mean of the two middle values). The rationale is taken from
    the successful attempt closest to the median total. If every attempt
    failed, the first error propagates so the caller falls back to the
    deterministic score.
    """
    ok = [v for v in verdicts if v.score is not None]
    run_detail = [
        {
            "score": (
                round(sum(v.scores.values()), 2) if v.score is not None else None
            ),
            "error": v.error,
        }
        for v in verdicts
    ]
    total_cap = sum(CRITERIA.values())
    if not ok:
        first = verdicts[0]
        return JudgeResult(
            error=first.error or "all judge attempts failed",
            raw=first.raw,
            cached=all(v.cached for v in verdicts),
            latency_ms=sum(v.latency_ms for v in verdicts),
            usage=_sum_usage([v.usage for v in verdicts]),
            runs=run_detail if len(verdicts) > 1 else None,
        )
    merged_scores = {k: _median([v.scores[k] for v in ok]) for k in CRITERIA}
    median_total = sum(merged_scores.values())
    nearest = min(ok, key=lambda v: abs(sum(v.scores.values()) - median_total))
    return JudgeResult(
        score=median_total / total_cap,
        scores=merged_scores,
        rationale=nearest.rationale,
        raw=None,
        cached=all(v.cached for v in verdicts),
        latency_ms=sum(v.latency_ms for v in verdicts),
        usage=_sum_usage([v.usage for v in verdicts]),
        runs=run_detail if len(verdicts) > 1 else None,
    )


class JudgeRunner:
    """Judge one task response via the shared client.

    ``runs`` > 1 issues N independent attempts (each with a distinct
    ``cache_salt`` so the attempts can't reuse each other's cache
    entries) and merges them into a per-criterion median verdict —
    mitigates single-verdict variance. Partial failures still produce a
    verdict; only a fully failed set yields ``score=None``.
    """

    def __init__(
        self,
        client: OpenAICompatClient,
        model: str,
        *,
        categories: set[str] | None = None,
        max_tokens: int = 512,
        runs: int = 1,
    ):
        self.client = client
        self.model = model
        self.runs = max(1, int(runs))
        raw = (
            set(categories)
            if categories is not None
            else set(DEFAULT_JUDGE_CATEGORIES)
        )
        self.judge_all = "*" in raw
        self.categories = raw - {"*"}
        self.gen = GenerationConfig(
            model=model, temperature=0.0, max_tokens=max_tokens
        )

    def applies(self, category: str) -> bool:
        return self.judge_all or category in self.categories

    def _judge_once(
        self, task: Task, response: str, salt: str | None = None
    ) -> JudgeResult:
        gen = self.gen
        if salt is not None:
            gen = GenerationConfig(
                model=self.gen.model,
                temperature=self.gen.temperature,
                max_tokens=self.gen.max_tokens,
                extra=dict(self.gen.extra),
                cache_salt=salt,
            )
        try:
            res = self.client.complete(gen, judge_messages(task, response))
        except ClientError as e:
            return JudgeResult(error=f"judge_error: {e}")
        scores, rationale, err = parse_judge_json(res.content)
        if err is not None:
            return JudgeResult(
                error=f"judge_parse: {err}",
                raw=(res.content or "")[:500],
                cached=res.cached,
                latency_ms=res.latency_ms,
                usage=res.usage,
            )
        total = sum(CRITERIA.values())
        score = sum(scores.values()) / total
        return JudgeResult(
            score=score,
            scores=scores,
            rationale=rationale,
            raw=None,
            cached=res.cached,
            latency_ms=res.latency_ms,
            usage=res.usage,
        )

    def judge(self, task: Task, response: str) -> JudgeResult:
        if self.runs == 1:
            return self._judge_once(task, response)
        # attempt 0 keeps the salt-free key so a prior runs=1 cache hit
        # is reused; later attempts get distinct keys via cache_salt.
        verdicts = [
            self._judge_once(task, response, None if i == 0 else f"jr-{i}")
            for i in range(self.runs)
        ]
        return _merge_verdicts(verdicts)
