# Memory — turkce-ai-karnesi

## State (after round 7, 2026-10-18)
- 8 rounds planned; 7 done. Suite green on sandbox: 163 tests.
- New: `summary.by_check_type` + "Check types" table in HTML/MD
  scorecards (worst-first, per-run columns; sparse-JSON fallback);
  `karne compare` takes N files (baseline = file 1, leaderboard +
  per-pair reports via `compare_many`/`format_multi`); OCR corpus
  8 → 11 templates (kira sözleşmesi, kargo etiketi, lab sonucu) —
  dataset 69 → 72 tasks.
- Next candidates (ROADMAP): `uv`/`pipx` quickstart check, tokenizer-
  aware length note, compare `--best` auto-baseline, CONTRIBUTING note,
  de/da morphology subset (still risky).

## Environment
- Tests/builds ONLY on sandbox: `cirak-run "python3 -m venv .venv &&
  .venv/bin/pip install -e '.[dev]' -q && .venv/bin/pytest -q"` from repo
  root (PEP 668 — venv mandatory). Generating YAML with python3 locally is
  fine (data emission, not a build/test).
- `./dataset` is a symlink → `src/turkce_karne/dataset` (canonical,
  ships in the wheel). `_`-prefixed yaml = sidecar (hashed, not loaded).
- Regenerate OCR file: `python3 scripts/gen_ocr_tasks.py`; freshness
  enforced by `tests/test_ocrnoise.py::test_generated_file_fresh`.

## Traps hit
- YAML flow list: `terms: [açıklama, not:]` → `not:` becomes a mapping
  key, not a string. Generator now JSON-quotes flow-list scalars.
- `edit` tool: never include the line(s) already following the range —
  it drops them (lost the judge template row once; restored).
- `_run` test helper hardcodes `concurrency=1`; pass overrides via
  `**{"concurrency": 1, **kw}` pattern (already fixed).
- Jinja2 `Undefined is not none` → true: `report` crashed on results
  JSONs missing new summary keys (`est_cost_usd`, `score_worst_rep`).
  `render_html` now setdefaults every template-touched key. Guard:
  `test_report_html_tolerates_sparse_json`.

## Decisions
See `docs/DECISIONS.md` (D1–D16). Highlights: deterministic checks are
ground truth; judge is bounded/advisory; `strict` = exact JSON key-set;
repeats measure sampling stability via cache-salt, not cache echoes;
bootstrap CIs seed from the data itself (no flag).
