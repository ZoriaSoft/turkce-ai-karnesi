# Contributing

Issues and pull requests are welcome. Code is MIT; everything under
`dataset/` is CC-BY-4.0 — by contributing dataset content you agree to
that license.

## Dataset tasks

One YAML file per category under `dataset/vN/` (currently `v1`). Each
item:

```yaml
- id: imla/de-da            # <category>/<slug>, unique — never reuse
  category: imla            # must match the file prefix
  difficulty: 3             # 1..5
  prompt: "…"               # instruction sent to the model
  input: |                  # optional document appended to the prompt
    …
  expected: {…}             # optional gold data (json_fields, written_form)
  checks:                   # what deterministic checks score
    - { type: contains, terms: ["sayın"] }
    - { type: count, unit: words, max: 40 }
  notes: "…"                # why the task/checks are shaped this way
```

Rules:

- **Original text only.** Write your own prompts, documents and expected
  answers. No copied articles, book passages, or copyrighted material.
- **Stable ids.** `<category>/<slug>`; once merged, never rename an id —
  result files pair tasks by id.
- **Deterministic first.** A task should be scorable by the built-in
  checks (see `karne validate` for required params). Judge-only tasks
  are out of scope for v1.
- **One thing per task.** Prefer many small tasks over one broad one.
- `notes:` explains traps (why an expected answer is the only right one).
- `_`-prefixed files (`dataset/v1/_exemplars.yaml`) are sidecars: hashed
  for reproducibility but not loaded as tasks.
- `dataset/v1/cikartim-ocr.yaml` is generated — edit
  `scripts/gen_ocr_tasks.py` instead and run
  `python3 scripts/gen_ocr_tasks.py` (its `--check` mode is also enforced
  by `tests/test_ocrnoise.py`).

Run `karne validate` before opening a PR; it lints ids, schema and check
params.

## Checks

New check types live in `src/turkce_karne/checks.py` (register in
`_CHECK_FN`) and must be deterministic, offline and explainable — a
failed check must say *why* in `detail`. Turkish spelling scanners go in
`src/turkce_karne/spelling.py` and must stay high-precision: only fire
on cases with no legal reading.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest           # fake model server; never calls real APIs
.venv/bin/karne validate   # dataset lint
.venv/bin/python scripts/gen_ocr_tasks.py --check   # generated OCR tasks fresh
```

There is no hosted CI: please run `pytest` and `karne validate` locally
before opening a PR and paste the summary line (e.g. `NNN passed`) in the
PR description.

Determinism matters: dataset hashing, seeded sampling and cache keys
over (model, messages, generation params) — please don't introduce
nondeterminism.
