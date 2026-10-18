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

## [Unreleased] — round 3 (2026-10-18)

### Added
- `spelling_rules` check + `turkce_karne/spelling.py`: four deterministic
  TDK scans that only fire on unambiguous errors — question particle
  glued to a word (`geliyormusun`, `gelmişmi`), wrong particle vowel
  (`akşam mi`), `-ki` left separate after locative/ablative or time
  adverbials (`evde ki`, `bugün ki`), and canonical fused-form
  misspellings (`herşey`, `yanlız`, `yada`, `dahada`...). Spec knobs:
  `rules` subset, `allow` stems, `max_violations`; partial credit
  0.25 per violation, violation list in check detail.
- `--prompt-style zero|fewshot|cot`: `fewshot` prepends one worked
  example per category from `dataset/v1/_exemplars.yaml`; `cot` appends
  a fixed "Önce adım adım düşün" suffix. Style enters the config
  fingerprint, cache key and results JSON `config.prompt_style`.
- `_`-prefixed dataset sidecar files: hashed into the dataset sha256
  but never loaded as tasks (`load_exemplars`).
- Per-category grouped bar chart in the HTML scorecard — inline SVG,
  still zero external assets; shown when ≥2 runs or ≥2 categories.
- `--dry-run` now echoes style/judge config and prints a rough
  token + USD estimate (4-chars/token heuristic).

### Changed
- Dataset v1: `spelling_rules` added to all `eposta`, `resmi-yazi`,
  `ozet` tasks and the three EN→TR `ceviri` tasks; two new
  free-write `imla` tasks — 59 → 61 items. `items_sha256` and
  `dataset` digests change; scores are not comparable with
  pre-round-3 runs.
- Turkish lexicon for `turkish_share` and the `mi_harmony` stem gate:
  ~170 → ~780 entries.

## [Unreleased] — round 4 (2026-10-18)

### Added
- `--judge-runs N` (1–9, default 1): the judge grades each response N
  times and the merged verdict is the per-criterion median, mitigating
  single-verdict variance. Attempts send identical payloads but get
  distinct cache keys via `GenerationConfig.cache_salt` (cache-key
  only, never on the wire); attempt 0 reuses the plain runs=1 cache
  entry. Partial failures still produce a verdict — `runs` detail and
  `n_errors` appear in the task's `judge` block; run-level
  `judge.runs` joins the results JSON and config fingerprint.
- `karne compare --checks`: per-check verdict flips paired by position
  inside each shared task (check index, type, pass/fail in A and B,
  `type_changed` and `checks_len_changed` spec-drift markers) plus a
  `n_check_flips` total — shows which specific check moved a score,
  in text and `--json` output.
- `FakeOpenAIState.responder` hook in tests for stateful per-request
  canned responses.

### Changed
- Sandbox test recipe in AGENTS.md now uses a venv (system pip is
  PEP 668 externally-managed on the Debian 13 sandbox).

## [Unreleased] — round 5 (2026-10-18)

### Added
- `--repeat N` now performs N real generations per task: each rep>0
  gets a `cache_salt` on the model call (rep 0 keeps the plain cache
  entry), so repeats measure sampling stability instead of echoing a
  cached response. `TaskScore.rep` is stored in the results JSON; the
  summary gains `n_rep_unstable` + `rep_unstable` (tasks whose
  pass/fail verdict flips across reps) and `karne compare` pairs
  `id@repN` keys so rep k of run A compares to rep k of run B.
- Seeded OCR-noise generator: `turkce_karne/ocrnoise.py` renders
  template documents where `{field}` placeholders keep
  equivalence-preserving display forms (TR/EN number formats, alternate
  date spellings, Turkish-aware case drift) while all other text gets
  realistic scan noise (diacritic folding, O/0-l/1-S/5 misreads, stray
  spaces, punctuation jitter, indents, separator artifacts).
  `scripts/gen_ocr_tasks.py` emits `dataset/v1/cikartim-ocr.yaml` —
  8 new extraction tasks (61 → 69) — and `--check` fails when the
  committed file is stale.
- HTML scorecard: `@repN` marker on repeated task rows and a
  reps/unstable line in run meta.

### Changed
- `json_fields` `strict: true` is now enforced (it was a silently
  ignored spec key): a response JSON containing keys absent from
  `expected` fails the check, with offenders listed in `detail.extra`.
  Keys matched via the nested-suffix alias do not count as extra.
  Existing `strict: true` tasks (all `cikartim/*` incl. the 8 new OCR
  ones) become stricter — scores not comparable with pre-round-5 runs
  on those tasks.
- `karne run --dry-run` prints distinct tasks plus `xN reps = M
  requests` when `--repeat > 1` (was: misleading request count).
