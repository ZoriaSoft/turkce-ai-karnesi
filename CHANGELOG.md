# Changelog

All notable changes to this project are documented here.
Format loosely follows Keep a Changelog; versions are dataset/tool aware.

## [Unreleased] — round 1 (2026-10-18)

### Added
- `turkce_karne` package: dataset loader/validator, deterministic check
  registry, OpenAI-compatible client (retry, cache, rpm limit, cost/latency),
  runner, Jinja2 HTML scorecard, `karne` CLI (`list`, `run`, `report`,
  `validate`).
- Dataset v1 (`dataset/v1/`): 24 original Turkish tasks across 8 categories —
  resmi yazi, eposta, ozet, cikartim (fatura + tutanak), imla, yonerge,
  ceviri, akl-yurutme. CC-BY-4.0.
- Fake OpenAI-compatible test server + pytest suite covering checks, dataset
  validation, client retry/cache, runner end-to-end, HTML render.
- Reproducibility: dataset sha256 + item digest, sorted results, seeded
  `--sample`, config fingerprint in every results JSON.

## [Unreleased] — round 2 (2026-10-18)

### Added
- Optional LLM judge (`turkce_karne/judge.py`): fixed 0–3 rubric over
  `instruction_following`, `turkish_quality`, `correctness`; strict-JSON
  contract with fallback to deterministic score on parse errors.
  Separate endpoint/key via `--judge-*` flags or `KARNE_JUDGE_*` env;
  cached like model calls. Blend `det*(1-w)+judge*w` (default w=0.4);
  `det_score` + per-criterion verdicts kept in results JSON and HTML.
- `karne compare a.json b.json`: paired per-task diff, flip counts
  (improve/regress) and McNemar significance test (exact binomial <25
  discordant pairs, continuity-corrected chi-square otherwise);
  `--json` for machine output.
- New `written_form` check: correct vs incorrect written forms in one
  spec with partial credit — covers "fix the spelling" tasks where a
  bad response can both contain the fix and keep the error.
- Dataset v1 expanded 24 → 59 tasks (+4 per category): new tutanak
  types (trafik, site, yoklama), reçete/sipariş extraction, harder
  akıl-yürütme, uzun özet budgets, more imla and format-strict yonerge.

### Changed
- Results JSON: per-task `det_score` and `judge` blocks; run-level
  `judge` section (model, weight, judged/error counts, judge cost).
- HTML scorecard: judge model/weight in run meta, det+judge breakdown
  per task, conditional footer text.
