# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). Dataset changes that affect scores
are called out explicitly.

## [Unreleased]

### Fixed
- `karne run` reads the model from `KARNE_MODEL` (as documented) and applies
  `KARNE_TEMPERATURE` / `KARNE_TIMEOUT`; CLI defaults no longer shadow them.
- A run where every request failed now exits 2 with the first error instead
  of reporting 0% as success; partial failures print a warning.
- `list` / `report` / `compare` print a one-line error for missing or
  malformed files instead of a traceback; output piped into `head` no longer
  raises `BrokenPipeError`.
- `compare --best` no longer treats a 0.0 score as missing.
- Empty completions are no longer cached (a transient failure used to replay
  on every rerun); cache temp files are unique per writer.

### Security
- LLM judge: the graded response is fenced as untrusted data so the model
  under test cannot steer its own verdict as easily. Judge cache keys change
  once.

### Packaging
- License expression `MIT AND CC-BY-4.0`; the dataset license now ships in
  the wheel. The sdist includes `tests/conftest.py` and the OCR generator.
- Added `SECURITY.md` and project URLs.

## [0.1.0] - 2026-10-19

First public release.

### Added

**Dataset v1** (CC-BY-4.0): 73 original Turkish tasks in 8 categories —
`resmi-yazi`, `eposta`, `ozet`, `cikartim`, `imla`, `yonerge`, `ceviri`,
`akl-yurutme`.
- Extraction tasks over fatura, tutanak (traffic, building, attendance),
  reçete, sipariş and irsaliye documents.
- 11 extraction tasks generated with seeded OCR noise
  (`turkce_karne/ocrnoise.py`, `scripts/gen_ocr_tasks.py`): template fields
  keep equivalence-preserving display forms (TR/EN number formats, alternate
  date spellings, Turkish-aware case drift) while surrounding text gets
  realistic scan noise. Templates include a rental contract, a cargo label
  and a lab report with reference-range distractors. `--check` fails when
  the committed file is stale.
- `_`-prefixed sidecar files (e.g. `_exemplars.yaml`) are hashed into the
  dataset digest but never loaded as tasks.

**Deterministic checks**: `contains`/`not_contains`, `answer_in`,
`answer_line`, `every_line_matches`, `only_lines_with_prefix`, `count`
(chars/words/sentences/lines), `word_order`, `starts_with`/`ends_with`,
`json_fields`, `turkish_share`, `regex`, `no_refusal`, and:
- `written_form`: correct vs incorrect written forms with partial credit.
- `spelling_rules`: five high-precision TDK scans that only fire on
  unambiguous errors — question particle glued to a word (`geliyormusun`),
  wrong particle vowel (`akşam mi`), separated `-ki` after locatives and
  time words (`bugün ki`), canonical fused-form errors (`herşey`, `yanlız`,
  `yada`), and separated de/da with the wrong vowel (`ben da`, `okul de`).
  Spec knobs: `rules`, `allow`, `max_violations`.
- `json_fields` with `strict: true` fails on keys absent from `expected`
  (offenders listed in `detail.extra`).
- Turkish-aware normalization (`I`→`ı`, `İ`→`i`) plus a Latin view so
  English terms still match; a ~780-entry lexicon for `turkish_share`.

**Runner and client**
- OpenAI-compatible client with retries (exponential backoff + jitter),
  content-addressed file cache, rpm pacing, token, latency and cost capture.
- Reproducibility: dataset sha256, item digest and config fingerprint in
  every results JSON; seeded `--sample`.
- `--repeat N` performs N real generations per task; the summary reports
  tasks whose verdict flips across repetitions plus worst/best rep rollups.
- `--prompt-style zero|fewshot|cot`.
- `--dry-run` prints the selection with a rough token and cost estimate.
- `summary.ci95`: cluster-bootstrap 95% CI on the run mean, seeded from the
  scores (reproducible, no numpy).
- `summary.by_check_type`: per-check-type means, worst first.

**Optional LLM judge**: fixed 0–3 rubric (`instruction_following`,
`turkish_quality`, `correctness`) with a strict JSON contract, separate
endpoint/key (`--judge-*`, `KARNE_JUDGE_*`), blend `det*(1-w)+judge*w`
(default `w=0.4`), and `--judge-runs N` for a per-criterion median verdict.

**Reports and comparison**
- Static HTML scorecard (no external assets) with per-category SVG chart,
  check-type table and expandable responses; `karne report --format md`.
- `karne compare`: paired per-task diff, improvement/regression flips,
  McNemar test, paired bootstrap CI on the mean delta, `--checks` for
  per-check flips, 3+ files as a leaderboard against a baseline, `--best`
  to pick the top run as baseline, `--json` output.
- Published October 2026 scorecard in `docs/results/2026-10/` (6 models ×
  73 tasks).

**CLI**: `karne list`, `validate`, `run`, `report`, `compare`.

### Fixed (dataset v1, found by the first full run)
- `imla/mi-mi`: the gold answer is "mü" (Süt mü?), not "mı".
- `imla/ki`: options B–D (belki, oysaki, sanki) are also written fused;
  replaced so A is the only correct answer.
- `ozet/veli-duyurusu`: term `şenlik` → stem `şenli` (k/ğ softening).
- `resmi-yazi/veli-toplantisi`: term `1400` could never match `14:00` after
  punctuation stripping; now `14:00` (also matches `14.00`).
- `cikartim/irsaliye`: gold `gonderen`/`alici` are now the verbatim field
  values from the document.

[Unreleased]: https://github.com/ZoriaSoft/turkce-ai-karnesi/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ZoriaSoft/turkce-ai-karnesi/commits/v0.1.0
