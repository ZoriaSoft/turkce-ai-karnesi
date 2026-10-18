# Memory — turkce-ai-karnesi

## State (after round 6, 2026-10-18)
- 8 rounds planned; 6 done. Suite green on sandbox: 153 tests.
- New: `turkce_karne/stats.py` seeded cluster-bootstrap → `summary.ci95`
  + `compare` `delta_ci95`; rep rollups `score_worst_rep`/`best_rep`;
  `karne report --format md`; `.github/workflows/ci.yml`; smarter
  `--dry-run` output estimate (count-check targets / difficulty).
- Next candidates (ROADMAP): per-check-type pass-rate table, >2-run
  compare, `uv run`/`pipx` quickstart check, more OCR templates,
  tokenizer-aware length checks.

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
