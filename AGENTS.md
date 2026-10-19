# Agent notes

- This repo builds an open-source evaluation kit for Turkish-capable LLMs.
- Layout:
  - `src/turkce_karne/` — package (dataset loader, checks, client, runner, report, cli).
  - `dataset/v1/` — the dataset (YAML, CC-BY-4.0); also bundled into the wheel.
  - `tests/` — pytest; uses a local fake OpenAI-compatible server, never real APIs.
  - `docs/results/` — published scorecards (results JSON + generated HTML/Markdown).
- Conventions: English code/docs, short `README.tr.md` in Turkish, MIT code,
  CC-BY-4.0 dataset. No secrets or internal hosts in the repo; env vars only.
- Determinism matters: dataset hashing, seeded sampling, cache keys over
  (model, messages, generation params). Do not introduce nondeterminism.
- Dataset contributions: one YAML file per category under `dataset/vN/`;
  keep IDs `<category>/<slug>`, unique and stable once published.
- Before committing: `python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' -q
  && .venv/bin/pytest -q && .venv/bin/karne validate` (there is no hosted CI).
- Local, untracked environment notes may live in `MEMORY.md` (gitignored);
  read it first if present.
