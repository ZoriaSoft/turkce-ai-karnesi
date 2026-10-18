# Agent notes

- This repo builds an open-source evaluation kit for Turkish-capable LLMs.
- Never run builds/tests locally. Use `cirak-run "<command>"` from the repo root;
  set `CIRAK_TIMEOUT=<s>` (max 1500) for long runs.
- Layout:
  - `src/turkce_karne/` — package (dataset loader, checks, client, runner, report, cli).
  - `dataset/v1/` — the dataset (YAML, CC-BY-4.0); also bundled into the wheel.
  - `tests/` — pytest; uses a local fake OpenAI-compatible server, never real APIs.
- Conventions: English code/docs, short `README.tr.md` in Turkish, MIT code,
  CC-BY-4.0 dataset. No secrets or internal hosts in the repo; env vars only.
- Determinism matters: dataset hashing, seeded sampling, cache keys over
  (model, messages, generation params). Do not introduce nondeterminism.
- Dataset contributions: one YAML file per category under `dataset/vN/`;
  keep IDs `<category>/<slug>`, unique and stable once published.
- Before committing: `cirak-run "python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' -q && .venv/bin/pytest -q"` (system pip is PEP 668 externally-managed — always use a venv on the sandbox).
