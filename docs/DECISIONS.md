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
