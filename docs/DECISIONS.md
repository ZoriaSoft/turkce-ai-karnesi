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
