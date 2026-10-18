# Decisions

## D1 — Deterministic checks before an LLM judge
Round 1 ships only rule-based checks. They are reproducible, free, and
explainable; a judge with a fixed rubric can layer on later without changing
task format (`checks:` list is open).

## D2 — Dataset lives in the package, symlinked at repo root
`src/turkce_karne/dataset/` is canonical so `pip install` ships the data.
`./dataset` symlinks to it for contributor convenience. The loader prefers
`--dataset`/cwd paths, then falls back to the bundled copy.

## D3 — OpenAI-compatible only
One client (`/chat/completions`) keeps the surface small; virtually every
provider (OpenAI, DeepSeek, Gemini via compat, Ollama, vLLM, Groq) exposes
this shape.

## D4 — Normalization is Turkish-aware
`I`→`ı`, `İ`→`i` folding + punctuation stripping before substring checks.
ASCII `i` is NOT treated as a Turkish signal char (it's everywhere in
English); dotless `ı` is.

## D5 — Partial credit only where meaningful
Task score = mean of check verdicts; failed checks contribute `fraction`
(0 by default). `json_fields` and `turkish_share` set fractions, everything
else is binary — a wrong `Cevap:` line earns 0, not pity points.

## D6 — No model name in repo docs
Env vars + CLI flags carry the endpoint/model; no provider-specific code.
Built-in price table is a small convenience, overridable by env.

## D7 — Judge is optional, bounded, and never authoritative
A second model may grade free-text categories with a fixed 0–3 rubric
(instruction_following, turkish_quality, correctness). The judge speaks
strict JSON only; parse/range failures fall back to the deterministic
score. Blend is `det*(1-w) + judge*w` with `w` defaulting to 0.4, and
both components stay in the results JSON — a judge can only *adjust*,
never silently replace, the check verdicts. Judge calls reuse the same
cache/retry/rpm path so reruns stay reproducible and cheap.

## D8 — Paired comparison over loose leaderboard diffs
`karne compare` pairs tasks by id and runs McNemar's test on flips
(exact binomial under 25 discordant pairs, continuity-corrected
chi-square above). Mean deltas alone hide whether changes are real;
a binary pass/fail discordance test is the standard answer for "did B
actually improve on A" and needs no extra dependencies.

## D9 — `spelling_rules` flags only unambiguous violations
Turkish orthography is full of context-dependent rules (de/da clitic vs
locative suffix needs parsing). The check deliberately covers only cases
with no legal reading: the question particle glued to a word, wrong
question-particle vowel, `-ki` separated after locatives/time words, and
a fixed TDK error list (`herşey`, `yanlız`...). Anything morphology-
dependent is skipped — a benchmark that sometimes penalizes correct
answers is worse than one that misses some errors.

## D10 — Prompt styles are fixed and dataset-bound
`--prompt-style` is part of the config fingerprint and the cache key:
`zero` (default), `fewshot` injects one worked example per category from
`dataset/v1/_exemplars.yaml` (a sidecar file: hashed into the dataset
digest, never loaded as a task), `cot` appends a fixed Turkish
think-step-by-step suffix. Styles are never mixed inside a run; comparing
`zero` vs `fewshot` scores across runs is how prompt sensitivity is
measured.

## D11 — Sidecar dataset files start with `_`
Files matching `dataset/vN/_*.yaml` are hashed into the dataset sha256
(so results stay reproducible) but skipped by the task loader. This is
how exemplars ship without becoming tasks.

## D12 — Charts are inline SVG, zero-asset
The per-category bar chart in the scorecard is generated SVG inside the
same single-file HTML — no JS, no fonts, no network. Consistent with the
report's existing zero-dependency stance.

## D13 — Repeats are real generations, not cache echoes
`--repeat N` used to duplicate the task list and serve reps 2..N from
the cache — the "stability" signal was meaningless. Now each rep>0 gets
a `cache_salt` on the model call (rep 0 reuses the plain cache entry),
so every rep is an independent sample. Compare pairs `id@repN`; the
run summary lists tasks whose verdict flips across reps.

## D14 — `json_fields` `strict` means exact key-set
The `strict` spec key existed in tasks since round 1 but was never read.
It now means: no response keys outside `expected` (nested-suffix alias
matches don't count as extra — a wrapper object holding the right
fields stays legal). Extras fail the check and land in `detail.extra`.
The alternative (fraction-penalize extras) was rejected: `strict` on
an extraction task means "only JSON with these fields", a binary ask.

## D15 — OCR corpus is generated, not hand-written
Bad-scan inputs are synthesized from templates by
`turkce_karne/ocrnoise.py` + `scripts/gen_ocr_tasks.py`: field
placeholders render equivalence-preserving display forms (TR/EN number
formats, alternate date spellings, case drift) so canonical expected
values still score, while surrounding text gets seeded noise
(diacritic folding, O/0, l/1, S/5 misreads, spacing jitter). One seed
per template keeps the YAML byte-reproducible; `scripts/gen_ocr_tasks.py
--check` proves the committed file is fresh. Hand-writing the same
noise would be unreviewable; the generator is the reviewable artifact.
