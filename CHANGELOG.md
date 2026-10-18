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
