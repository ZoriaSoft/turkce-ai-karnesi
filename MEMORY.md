# Memory — turkce-ai-karnesi

## State (after round 5, 2026-10-18)
- 8 rounds planned; 5 done. Suite green on sandbox: 138 tests.
- Dataset: 69 tasks / 8 categories (incl. 8 generated `cikartim-ocr.yaml`).
- Scoring: deterministic checks + optional judge; `--repeat N` = N real
  generations (cache-salt), `rep_unstable` summary; compare pairs `id@repN`.
- Next candidates (ROADMAP): HTML golden-file test, CI when public,
  `uv run`/`pipx` quickstart check, rep-aware score aggregation,
  more OCR templates, `--dry-run` model-aware estimate.

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

## Decisions
See `docs/DECISIONS.md` (D1–D15). Highlights: deterministic checks are
ground truth; judge is bounded/advisory; `strict` = exact JSON key-set;
repeats measure sampling stability via cache-salt, not cache echoes.
