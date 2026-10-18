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

## Round 2 candidates
- [ ] Expand dataset to ~60 tasks; deepen weak categories (tutanak OCR, daha
      zor akıl yürütme, uzun özet).
- [ ] LLM judge: fixed rubric (0-3 per criterion), judge = separate
      `--judge-model`, cached like model calls; blended score = deterministic
      + judge weight configurable.
- [ ] Turkish spell-rule checks beyond lexicon: de/da clitic vs suffix
      heuristic, question particle mi/mı/mu/mü harmony check.
- [ ] `karne compare a.json b.json` — side-by-side diff, significance of
      per-task flips.
- [ ] Per-category HTML breakdown + per-task expandable raw outputs.
- [ ] Prompt sets: `--prompt-style zero|fewshot|cot` with fixed templates.
- [ ] Pricing table for common TR-relevant cheap models; `karne price-estimate`.
- [ ] GitHub Actions CI (when public): pytest + dataset lint + build check.
- [ ] `uv run` / `pipx` quickstart verification on a clean env.
- [ ] Multimodal-free "OCR-like" generator: seeded noise injector to synthesize
      more fatura/tutanak inputs deterministically.
- [ ] Turkish tokenizer-aware length checks (BPE vs word discrepancy note).

## Known limits / decisions
- `json_fields` extracts first balanced `{...}` block; nested braces OK.
- `turkish_share` uses a small built-in lexicon; threshold-based, heuristic.
- Judge deliberately absent in v1; deterministic checks must carry the signal.
- Concurrency is client-side only; deterministic regardless of interleaving
  because cache keys are content-based.
