# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub's
[private vulnerability reporting](https://github.com/ZoriaSoft/turkce-ai-karnesi/security/advisories/new)
rather than a public issue. Include steps to reproduce and the affected
version or commit. We aim to acknowledge reports within a few days.

## Scope notes

- `karne` sends prompts to the endpoint you configure and stores responses
  in `.karne-cache/` and `results/`. Treat both as potentially sensitive if
  you evaluate private prompts; neither is committed by the default
  `.gitignore`.
- API keys are read from flags or environment variables and are never
  written to results files, the cache, or the run fingerprint.
- Model responses are untrusted input. They are HTML-escaped in the
  scorecard and fenced as data when shown to the optional LLM judge.
