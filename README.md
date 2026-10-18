# turkce-ai-karnesi

An evaluation kit that answers one question: **which LLMs are actually good
at real Turkish work?** Especially the cheap/free ones people actually use.

No vibes, no leaderboards scraped from elsewhere — a fixed dataset of
original Turkish tasks scored by deterministic, reproducible checks, plus an
HTML scorecard you can diff across models.

Türkçe özet: [`README.tr.md`](README.tr.md)

## The problem

Public benchmarks (MMLU-style) test translated trivia, not whether a model
can write a proper `dilekçe`, keep `de/da` and `ki` straight, extract fields
from a messy `fatura`, or follow "exactly 3 bullet points, max 6 words each"
in Turkish. This kit tests that.

## 30-second quickstart

```bash
pip install -e .
export KARNE_BASE_URL=https://api.openai.com/v1   # any OpenAI-compatible endpoint
export KARNE_API_KEY=sk-...
export KARNE_MODEL=gpt-4o-mini

karne validate                        # sanity-check the dataset
karne run --model $KARNE_MODEL --html # run all tasks, write JSON + HTML
karne report results/karne-*.json --out scorecard.html
```

Or run without installing: `uvx --from . karne validate` (pipx equivalent:
`pipx run --spec . karne validate`).

Outputs land in `results/` (JSON per run) plus a static HTML scorecard with
per-task expandable responses.

## What gets tested

73 original tasks (dataset v1, CC-BY-4.0) across 8 categories:

| Category      | What it measures                                   |
|---------------|----------------------------------------------------|
| `resmi-yazi`  | Dilekçe format: kurum → Sayın → metin → tarih/imza |
| `eposta`      | Konu: line, greeting, closing                      |
| `ozet`        | Summaries under hard word/sentence budgets         |
| `cikartim`    | Field extraction (JSON) from OCR-like fatura/tutanak — 11 of them generated with seeded OCR noise (`scripts/gen_ocr_tasks.py`) |
| `imla`        | de/da, ki, soru eki mi/mı, bitişik yazım           |
| `yonerge`     | Strict format: prefixes, line counts, no dots      |
| `ceviri`      | TR↔EN content-word accuracy                        |
| `akl-yurutme` | Turkish word problems, `Cevap: X` answer line      |

Every task is scored by checks like `contains`, `word_order`,
`every_line_matches`, `json_fields`, `count`, `turkish_share`,
`answer_in`, `written_form`, `spelling_rules` — all deterministic and
offline. A task's score is the mean of its check verdicts (partial credit
for `json_fields`, `turkish_share`, `written_form`, `spelling_rules`).

`spelling_rules` scans the response for unambiguous TDK violations:
the question particle glued to a word (`geliyormusun`), wrong question-
particle vowel (`akşam mi`), separated `-ki` after locatives/time words
(`bugün ki`), canonical fused-form errors (`herşey`, `yanlız`, `yada`),
and the separated `de/da` clitic with the wrong vowel for the preceding
word (`ben da`, `okul de`). Morphology is not modeled — attached
`…de/da` (locative vs clitic) stays out of scope, and the check only
fires on cases with no legal reading. Task specs can subset rules,
`allow` stems, or tolerate `max_violations`.

Optionally, a second model can act as a judge on the free-text
categories (`--judge-model`), adding a fixed-rubric score that blends
with the deterministic score.

## How it works

```
task (YAML) ──> chat.completions ──> deterministic checks ──> score
     │                  │                    │
  dataset v1      cached, retried,      pass/fail + detail
  (hashed)        rpm-limited client   per task & category
```

- **Reproducible**: results JSON embeds the dataset sha256, an item digest,
  and a config fingerprint. Same endpoint + same dataset → same score.
- **Cache**: content-addressed (`model+messages+params`), on by default
  (`.karne-cache/`); `--cache off` disables. Reruns are free.
- **Retries**: exponential backoff with jitter on 429/5xx/timeouts;
  4xx fails fast. `--rpm` paces requests.
- **Cost/time**: token usage captured per task; USD estimate via
  `KARNE_PRICE_IN`/`KARNE_PRICE_OUT` or the built-in mini table.
- **Uncertainty**: `summary.ci95` is a cluster-bootstrap 95% CI on the
  mean (reps of one task resampled together; seeded from the scores, so
  reproducible). With `--repeat N`, `score_worst_rep`/`score_best_rep`
  bound the spread across repetitions.

## CLI

```bash
karne list [--categories imla,ceviri]     # show tasks
karne validate                            # dataset + check-spec lint
karne run --model M [--tasks id1,id2] [--sample 10 --seed 7]
          [--repeat 3] [--concurrency 4] [--rpm 60]
                         # --repeat N = N real generations/task (cache-key
                         # salt); summary reports verdict flips across reps
          [--prompt-style zero|fewshot|cot]
          [--judge-model J --judge-weight 0.4 --judge-runs 3]
          [--out results/x.json] [--html]
karne report a.json b.json --out compare.html   # multi-model scorecard
karne report a.json --format md                 # Markdown table (stdout or --out)
karne compare a.json b.json [--json] [--checks]  # paired diff + flips + delta CI
karne compare base.json b.json c.json           # N runs: all vs first file
karne compare a.json b.json c.json --best       # baseline = top-scoring run
```

Useful flags: `--dry-run` prints the selection plus a rough token/cost
estimate without calling the API; `--label` names a run in reports;
`--system-prompt` overrides the default Turkish system prompt;
`--prompt-style fewshot` prepends a fixed per-category exemplar
(`dataset/v1/_exemplars.yaml`) and `--prompt-style cot` appends a fixed
"think step by step" suffix — both change the cache key and the config
fingerprint, so runs stay comparable within a style.

### LLM judge

```bash
karne run --model cheap-model --judge-model stronger-model --html
```

The judge grades each response on three fixed criteria (0–3 each):
`instruction_following`, `turkish_quality`, `correctness`. It must answer
with strict JSON; parse failures fall back to the deterministic score.

- Judge calls use their own credentials: `--judge-base-url`,
  `--judge-api-key`, or `KARNE_JUDGE_BASE_URL` / `KARNE_JUDGE_API_KEY`
  (default: same endpoint/key as the model under test).
- By default only free-text categories are judged:
  `resmi-yazi`, `eposta`, `ozet`, `ceviri`. Widen with
  `--judge-categories a,b` or `all`.
- Final score = `det * (1 - w) + judge * w` where `w` is
  `--judge-weight` (default 0.4). `det_score` and the per-criterion
  verdicts stay in the results JSON and HTML.
- `--judge-runs N` (1–9, default 1) judges each response N times and
  keeps the per-criterion median verdict — mitigates single-verdict
  variance. Attempts share the wire payload but get distinct cache keys;
  partial failures still produce a verdict (`n_errors` in the JSON).

### Comparing runs

`karne compare a.json b.json` pairs tasks by id (and `@repN` when
`--repeat` was used) and reports score deltas, flip counts (fail→pass
improvements, pass→fail regressions), a McNemar significance test
(exact binomial under 25 discordant pairs, chi-square with continuity
correction above) and a paired bootstrap 95% CI on the mean score delta
(`delta_ci95` — resamples are seeded from the data, so the same two
files always print the same interval).

`karne compare a.json b.json --checks` additionally reports per-check
verdict flips (check position, type, pass/fail in A and B) — a task
score can move because one specific check flipped; `type_changed` marks
check-spec drift between the two runs.

With 3+ files (`karne compare base.json b.json c.json ...`), every run is
compared against the first file (the baseline): output starts with a
leaderboard (paired mean score over tasks shared with the baseline,
delta vs A, McNemar p) followed by the full per-pair reports; `--json`
returns `{baseline, leaderboard, comparisons}`. `--best` picks the
highest-scoring file as the baseline instead of the first file.

The scorecard also breaks scores down by check type: every run's
summary carries `by_check_type` (check-level mean — pass=1.0,
fail=partial credit or 0, plus `n` and `n_fail`), and the HTML/Markdown
report renders a worst-first "Check types" table so "which check types
fail most" is one glance — the same table shows per-run columns when
several results JSONs are reported together.

## Dataset

`dataset/v1/*.yaml`, one file per category (plus the generated
`cikartim-ocr.yaml` — edit `scripts/gen_ocr_tasks.py` instead and rebuild
with `python3 scripts/gen_ocr_tasks.py`). Schema per item:

```yaml
- id: cikartim/fatura        # <category>/<slug>, unique
  category: cikartim
  difficulty: 3              # 1..5
  prompt: "…"                # instruction sent to the model
  input: |                   # optional document appended to the prompt
    …
  expected: {…}              # optional gold data (e.g. for json_fields)
  checks:
    - { type: json_fields, strict: true }
    - { type: count, unit: words, max: 40 }
```

Run `karne validate` after editing; it checks ids, schema, and that every
check type exists with its required params. All text is original —
contributions welcome under CC-BY-4.0 (see `CONTRIBUTING.md`).

## Limits

- `turkish_share` is a lexicon+diacritics heuristic, not a language ID.
- The judge is a model too — it can be wrong or biased toward its own
  family's style. Deterministic checks stay the ground truth; the judge
  is a bounded 0–3 rubric, not free-form scoring.
- `json_fields` compares the expected fields; extra keys in the response
  are ignored unless the spec sets `strict: true` (then extras fail the
  check and are listed in `detail.extra`).
- Turkish morphology isn't modeled — de/da/ki correctness is tested via
  authored tasks, `written_form`, and the high-precision `spelling_rules`
  scans (unambiguous cases only); a general grammar check stays out of
  scope.
- `count` checks count words/lines/chars, not tokens — a model's BPE
  tokenizer splits agglutinated Turkish far more aggressively than a
  space-based word count suggests, so translate our limits to token
  budgets generously.


## Development

```bash
pip install -e .[dev]
pytest                 # fake model server; no real API calls
```

Code is MIT; the dataset is CC-BY-4.0 (see `dataset/` headers).
