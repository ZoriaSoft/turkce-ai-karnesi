# Roadmap

## Name proposal
`turkish-llm-scorecard` — checked 2026-10-18, zero GitHub repos with that
name (API search). Alternatives: `turkce-karne`, `tr-llm-karne`. Owner decides;
repo/directory/remote keep the current name until then.

## Round 1 (done)
- [x] Repo scaffold: pyproject (src layout, `turkce_karne` module), MIT license,
      README (+TR), CI-friendly pytest setup.
- [x] Dataset v1: loader + validation, ~24 original tasks across 8 categories.
- [x] Deterministic checks: contains/not_contains, answer_in, every_line_matches,
      only_lines_with_prefix, count (chars/words/sentences/lines), word_order,
      starts_with/ends_with, json_fields, turkish_share, regex.
- [x] OpenAI-compatible client: chat completions, retries with backoff+jitter,
      JSON file cache, rpm rate limit, token/cost/latency tracking, concurrency.
- [x] Runner: sampling (seeded), scoring, JSON results with dataset + config
      fingerprints for reproducibility.
- [x] Static HTML scorecard (Jinja2, no external assets) + `karne report`.
- [x] CLI: `karne list`, `karne run`, `karne report`, `karne validate`.
- [x] Tests with fake model server (no real API calls).

## Round 2 (done)
- [x] LLM judge: fixed 0-3 rubric (instruction_following, turkish_quality,
      correctness), strict-JSON contract, `--judge-model` + `KARNE_JUDGE_*`,
      cached like model calls, blended score det*(1-w)+judge*w (w=0.4),
      per-task det_score + judge verdicts in JSON/HTML.
- [x] `karne compare a.json b.json`: paired diffs, flips, McNemar test
      (exact <25 pairs, chi2-cc otherwise), `--json` output.
- [x] `written_form` check (correct vs incorrect forms, partial credit).
- [x] Dataset expanded to 59 tasks (+4/category): trafik/site/yoklama
      tutanak, reçete + sipariş extraction, harder akıl-yürütme, uzun özet,
      imla kisaltma/ek-ayrimi, format-strict yonerge.
- [x] HTML: judge meta per run, det+judge split per task, conditional footer.

## Round 3+ candidates
- [ ] Turkish spell-rule checks beyond authored tasks: de/da clitic-vs-suffix
      heuristic, mi/mı/mu/mü harmony check as reusable check types.
- [ ] Prompt sets: `--prompt-style zero|fewshot|cot` with fixed templates.
- [ ] Pricing table expansion for TR-relevant cheap models;
      `karne price-estimate` (dry-run token estimate, no API call).
- [ ] GitHub Actions CI (when public): pytest + dataset lint + build check.
- [ ] `uv run` / `pipx` quickstart verification on a clean env.
- [ ] Multimodal-free "OCR-like" generator: seeded noise injector to synthesize
      more fatura/tutanak inputs deterministically.
- [ ] Turkish tokenizer-aware length checks (BPE vs word discrepancy note).
- [ ] `--judge-runs N`: judge each response N times, median verdict
      (mitigates single-judge variance).
- [ ] Per-category radar/bar chart in HTML (inline SVG, still zero deps).
- [ ] `karne diff --checks`: show per-check verdict flips between two runs
      (compare currently operates at task level).

## Known limits / decisions
- `json_fields` extracts first balanced `{...}` block; nested braces OK.
- `turkish_share` uses a small built-in lexicon; threshold-based, heuristic.
- Judge is optional and bounded (0-3 rubric, strict JSON); deterministic
  checks stay ground truth; blend keeps `det_score` in the results.
- McNemar pairing assumes two runs share task ids; disjoint tasks are
  reported as `only_in_*`, not scored.
- Concurrency is client-side only; deterministic regardless of interleaving
  because cache keys are content-based.
