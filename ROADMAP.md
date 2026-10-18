# Roadmap

## Name proposal
`turkish-llm-scorecard` — checked 2026-10-18, zero GitHub repos with that
name (API search). Alternatives: `turkce-karne`, `tr-llm-karne`. Owner decides;
repo/directory/remote keep the current name until then.

## Round 1 (done)
- [x] Repo scaffold: pyproject (src layout, `turkce_karne` module), MIT license,
      README (+TR), CI-friendly pytest setup.
- [x] Dataset v1: loader + validation, ~24 original tasks across 8 categories.
- [x] Deterministic checks: contains/not_contains, answer_in, every_line_matches,
      only_lines_with_prefix, count (chars/words/sentences/lines), word_order,
      starts_with/ends_with, json_fields, turkish_share, regex.
- [x] OpenAI-compatible client: chat completions, retries with backoff+jitter,
      JSON file cache, rpm rate limit, token/cost/latency tracking, concurrency.
- [x] Runner: sampling (seeded), scoring, JSON results with dataset + config
      fingerprints for reproducibility.
- [x] Static HTML scorecard (Jinja2, no external assets) + `karne report`.
- [x] CLI: `karne list`, `karne run`, `karne report`, `karne validate`.
- [x] Tests with fake model server (no real API calls).

## Round 2 (done)
- [x] LLM judge: fixed 0-3 rubric (instruction_following, turkish_quality,
      correctness), strict-JSON contract, `--judge-model` + `KARNE_JUDGE_*`,
      cached like model calls, blended score det*(1-w)+judge*w (w=0.4),
      per-task det_score + judge verdicts in JSON/HTML.
- [x] `karne compare a.json b.json`: paired diffs, flips, McNemar test
      (exact <25 pairs, chi2-cc otherwise), `--json` output.
- [x] `written_form` check (correct vs incorrect forms, partial credit).
- [x] Dataset expanded to 59 tasks (+4/category): trafik/site/yoklama
      tutanak, reçete + sipariş extraction, harder akıl-yürütme, uzun özet,
      imla kisaltma/ek-ayrimi, format-strict yonerge.
- [x] HTML: judge meta per run, det+judge split per task, conditional footer.

## Round 3 (done)
- [x] `spelling_rules` check + `spelling.py`: four high-precision TDK
      scans (question particle attached, particle vowel harmony, `-ki`
      separated, canonical fused-form traps), `rules`/`allow`/
      `max_violations` spec knobs, partial credit 0.25/violation.
      Wired into 24 free-prose tasks + 2 new imla tasks (59→61).
- [x] Turkish lexicon ~170 → ~780 entries (heuristics stay bounded).
- [x] `--prompt-style zero|fewshot|cot`: fewshot injects per-category
      exemplar from `dataset/v1/_exemplars.yaml` (new `_`-sidecar
      convention, hashed but not a task); cot appends a fixed suffix.
      Style joins config fingerprint + cache key + results JSON.
- [x] Per-category grouped bar chart in HTML scorecard (inline SVG,
      zero deps) — appears when ≥2 runs or ≥2 categories.
- [x] `--dry-run` token/cost estimate (4-chars/token heuristic) +
      style/judge echo in the plan.


## Round 4 (done)
- [x] `--judge-runs N` (1–9): N independent judge attempts per response,
      per-criterion median verdict, partial-failure tolerance (`n_errors`,
      `runs` detail in results). Attempts share the wire payload but get
      distinct cache keys via `GenerationConfig.cache_salt` (key-only,
      never sent); attempt 0 reuses the plain runs=1 cache entry.
- [x] `karne compare --checks`: per-check verdict flips paired by
      position (type, pass/fail in A and B, `type_changed` /
      `checks_len_changed` spec-drift marks), `n_check_flips` summary,
      text + `--json` output.
- [x] Fixed sandbox test recipe (PEP 668 venv) in AGENTS.md.

## Round 5 (done)
- [x] `--repeat N` now issues N real generations per task: each rep>0
      gets a `cache_salt` (rep 0 keeps the plain cache entry), results
      carry `rep` indices, the summary reports `n_rep_unstable` +
      `rep_unstable` (tasks whose pass/fail verdict flips across reps),
      and `karne compare` pairs `id@repN` keys instead of last-write-wins.
- [x] `json_fields` `strict: true` now enforced: response JSON with keys
      absent from `expected` fails (nested-suffix alias matches don't
      count as extra; `detail.extra` lists offenders). Was a dead spec
      key before.
- [x] Seeded OCR-noise generator (`turkce_karne/ocrnoise.py` +
      `scripts/gen_ocr_tasks.py`): template fields keep canonical values,
      surrounding text gets diacritic-folding/glyph-misread/spacing noise;
      emits `dataset/v1/cikartim-ocr.yaml` (8 tasks, 61→69). `--check`
      mode verifies the committed file is fresh.
- [x] HTML scorecard: `@repN` marker on repeated tasks, reps/unstable
      row in run meta.

## Round 6 (done)
- [x] `summary.ci95`: cluster bootstrap 95% CI on the run mean
      (`turkce_karne/stats.py`) — reps of a task resample together;
      seed derives from a SHA-256 of the scores so the interval is
      reproducible. In CLI output + HTML run meta.
- [x] `karne compare` `delta_ci95`: paired bootstrap CI on the mean
      score delta next to McNemar (effect size + significance).
- [x] `--repeat` rollups: `score_worst_rep` / `score_best_rep` in the
      summary, CLI, and HTML.
- [x] `karne report --format md`: Markdown scorecard (stdout or --out).
- [x] `.github/workflows/ci.yml`: pytest 3.11/3.13, karne validate,
      OCR freshness, dry-run smoke, wheel build + bundled-dataset check.
- [x] HTML scorecard structure test + `test_stats.py`.
- [x] `--dry-run` output estimate: `count`-check targets or difficulty
      scaling instead of a flat 400.

## Round 7 (done)
- [x] `summary.by_check_type`: check-level mean score + `n`/`n_fail` per
      check type (worst-first) in the results JSON; "Check types" table in
      the HTML + Markdown scorecards (per-run columns for multi-run
      reports; old JSONs fall back to task-level aggregation).
- [x] `karne compare` N files: every run vs the first (baseline);
      leaderboard (paired mean over shared tasks, delta, McNemar p) +
      full per-pair reports. `{baseline, leaderboard, comparisons}` JSON.
- [x] OCR templates +3: kira sözleşmesi, kargo etiketi, laboratuvar
      sonucu (reference-range distractors) — 69 → 72 tasks.

## Round 8 (done)
- [x] `spelling_rules` fifth scan `de_da_harmony`: separated de/da
      clitic vowel harmony ("ben da"→de, "okul de"→da); attached forms
      stay out of scope, loan stems (fetha / palatal-l), â/î/û stems
      and foreign fixed phrases skipped. Registered by default.
- [x] `karne compare --best`: highest-scoring file becomes the baseline
      (2-file and leaderboard modes).
- [x] `imla/de-da-uyum` task; dataset 72 → 73.
- [x] `uv run`/`uvx` quickstart verified on clean env (`uvx --from .
      karne validate`; pipx not in the sandbox image — documented as
      equivalent).
- [x] Final polish: `CONTRIBUTING.md`, README limits note that `count`
      measures words/chars not tokens (BPE agglutination gap), README.tr
      synced.

## Beyond round 8 (ideas, unscheduled)
- [ ] More OCR templates beyond 11 (hastane sevk, mahkeme kararı,
      sigorta poliçesi) once a template style settles.
- [ ] Generic de/da clitic-vs-suffix split needs real morphology; the
      separated-vowel subset shipped in round 8 covers the safe half.
- [ ] Public-name decision (`turkish-llm-scorecard` proposal above),
      PyPI/release once the repo goes public.

## Known limits / decisions
- `json_fields` extracts first balanced `{...}` block; nested braces OK.
- `turkish_share` uses a small built-in lexicon; threshold-based, heuristic.
- Judge is optional and bounded (0-3 rubric, strict JSON); deterministic
  checks stay ground truth; blend keeps `det_score` in the results.
- McNemar pairing assumes two runs share task ids; disjoint tasks are
  reported as `only_in_*`, not scored.
- Concurrency is client-side only; deterministic regardless of interleaving
  because cache keys are content-based.
- `--judge-runs` repeats identical judge payloads; the median mitigates
  serving-nondeterminism in the judge, not prompt or rubric bias.
- `strict: true` on `json_fields` counts keys found only via the
  nested-suffix alias as legitimate (wrapper objects don't fail strict).
- Bootstrap CIs are percentile-method (2000 resamples), seeded from the
  data — deterministic but not model-aware; tiny n still gives a narrow
  interval that understates real uncertainty (as every CI does at n=5).
- `by_check_type` mirrors `task_score_value` (pass=1, fail=fraction or 0);
  the "Check types" table reads `summary.by_check_type` when present and
  otherwise recomputes from `tasks[].checks`, so old JSONs still render.
- Multi-run `karne compare` treats file 1 as the baseline; the
  leaderboard's `paired_score` is each run's mean over tasks it shares
  with that baseline (not the run's own summary mean).
