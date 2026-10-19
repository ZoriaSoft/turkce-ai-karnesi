# Roadmap

## Name

The repository and the distribution are `turkce-ai-karnesi` (import module
`turkce_karne`, CLI `karne`). An English alias, `turkish-llm-scorecard`, may
be used later (for example as a mirror); no rename is planned before 0.2.

## Shipped in 0.1.0

Dataset v1 (73 tasks, 8 categories, seeded OCR-noise extraction tasks),
deterministic checks including `spelling_rules` and strict `json_fields`,
an OpenAI-compatible client with cache/retries/pacing, repeats with
stability metrics, bootstrap confidence intervals, an optional LLM judge
with median-of-N verdicts, HTML/Markdown scorecards and `karne compare`
(paired diff, McNemar, delta CI, leaderboards). See `CHANGELOG.md`.

## Next

- [ ] More OCR templates (hospital referral, court decision, insurance
      policy).
- [ ] Attached de/da (clitic vs locative suffix) needs real morphology; the
      separated-vowel subset covers the unambiguous half today.
- [ ] PyPI release as `turkce-ai-karnesi`.
- [ ] Re-run the published scorecard for each dataset version and add paid
      frontier models when credits allow.

## Known limits and design notes

- `json_fields` extracts the first balanced `{...}` block; nested braces
  are fine.
- `turkish_share` uses a built-in lexicon and a threshold — a heuristic,
  not language identification.
- The judge is optional and bounded (0–3 rubric, strict JSON).
  Deterministic checks stay the ground truth and `det_score` is always kept.
- McNemar pairing assumes two runs share task ids; disjoint tasks are
  reported as `only_in_*`, not scored.
- Concurrency is client-side; results are deterministic regardless of
  interleaving because cache keys are content-based.
- `--judge-runs` repeats identical judge payloads; the median smooths
  serving nondeterminism, not prompt or rubric bias.
- With `strict: true`, keys matched only via the nested-suffix alias count
  as legitimate, so wrapper objects do not fail.
- Bootstrap CIs are percentile intervals over 2000 resamples, seeded from
  the data. They are deterministic but, like any CI, understate uncertainty
  for very small samples.
- `by_check_type` mirrors task scoring (pass = 1, fail = fraction or 0);
  reports recompute it from `tasks[].checks` for older results files.
- In multi-run `karne compare`, the first file is the baseline and each
  run's `paired_score` is its mean over tasks shared with that baseline.
