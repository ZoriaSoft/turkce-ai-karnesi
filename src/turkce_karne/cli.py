"""karne — CLI entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .checks import check_types
from .dataset import categories, dataset_digest, load_dataset, resolve_dataset_dir
from .errors import CheckSpecError, ClientError, DatasetError
from .report import write_html
from .runner import RunConfig, load_results, run_eval, save_results
from .compare import compare_runs, format_compare


def _env_float(name: str, default: float) -> float:
    """Float from env var ``name``; ``default`` when unset or empty."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise SystemExit(f"karne: {name} must be a number, got {raw!r}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="karne",
        description="Evaluation kit for Turkish-capable LLMs.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    lp = sub.add_parser("list", help="List dataset tasks")
    lp.add_argument("--dataset", help="dataset dir (default: ./dataset or bundled)")
    lp.add_argument("--dataset-version", default="v1")
    lp.add_argument("--categories", help="comma-separated category filter")

    vp = sub.add_parser("validate", help="Validate dataset structure + check specs")
    vp.add_argument("--dataset", help="dataset dir")
    vp.add_argument("--dataset-version", default="v1")

    rp = sub.add_parser("run", help="Run the evaluation against a model")
    rp.add_argument("--base-url", help="OpenAI-compatible base URL "
                    "(or KARNE_BASE_URL)")
    rp.add_argument("--api-key", help="API key (or KARNE_API_KEY)")
    rp.add_argument("--model", help="model name (or KARNE_MODEL)")
    rp.add_argument("--dataset", help="dataset dir")
    rp.add_argument("--dataset-version", default="v1")
    rp.add_argument("--tasks", help="comma-separated task ids")
    rp.add_argument("--categories", help="comma-separated categories")
    rp.add_argument("--sample", type=int, help="sample N tasks (seeded)")
    rp.add_argument("--seed", type=int, default=42)
    rp.add_argument("--repeat", type=int, default=1,
                    help="repeat each task N times (each rep is a real "
                    "generation via a cache-key salt; reps measure "
                    "sampling stability — see n_rep_unstable)")
    rp.add_argument("--temperature", type=float, default=None,
                    help="sampling temperature (or KARNE_TEMPERATURE; default 0)")
    rp.add_argument("--max-tokens", type=int, default=2048)
    rp.add_argument("--concurrency", type=int, default=4)
    rp.add_argument("--rpm", type=float, help="requests per minute cap")
    rp.add_argument("--timeout", type=float, default=None,
                    help="request timeout in seconds (or KARNE_TIMEOUT; default 60)")
    rp.add_argument("--max-retries", type=int, default=4)
    rp.add_argument("--cache", default=".karne-cache",
                    help="cache dir (or 'off')")
    rp.add_argument("--out", help="results JSON path "
                    "(default results/karne-<model>-<ts>.json)")
    rp.add_argument("--html", nargs="?", const="", default=None,
                    help="also write an HTML scorecard (optional path)")
    rp.add_argument("--label", help="display name in reports")
    rp.add_argument("--system-prompt", help="override system prompt")
    rp.add_argument("--prompt-style", choices=["zero", "fewshot", "cot"],
                    default="zero",
                    help="zero (default) | fewshot = one exemplar per "
                    "category | cot = 'think step by step' suffix")
    rp.add_argument("--dry-run", action="store_true",
                    help="validate selection, print plan, no API calls")

    rp.add_argument("--judge-model", help="judge model (or KARNE_JUDGE_MODEL); "
                    "enables the LLM judge on judgeable categories")
    rp.add_argument("--judge-base-url", help="judge endpoint "
                    "(or KARNE_JUDGE_BASE_URL; default: same as model)")
    rp.add_argument("--judge-api-key", help="judge key "
                    "(or KARNE_JUDGE_API_KEY; default: same as model)")
    rp.add_argument("--judge-weight", type=float, default=0.4,
                    help="blend weight for judge score (0-1, default 0.4)")
    rp.add_argument("--judge-categories", default=None,
                    help="comma-separated categories to judge "
                    "('all' = every task; default: free-text categories)")
    rp.add_argument("--judge-runs", type=int, default=1,
                    help="judge each response N times, median verdict "
                    "(1-9, default 1; mitigates judge variance)")

    hp = sub.add_parser("report", help="Render results JSON(s) to HTML or Markdown")
    hp.add_argument("results", nargs="+", help="results JSON file(s)")
    hp.add_argument("--out", help="output path (required for html; "
                    "md prints to stdout when omitted)")
    hp.add_argument("--format", choices=["html", "md"], default="html")
    hp.add_argument("--title", help="report title")

    cp = sub.add_parser("compare", help="Paired diff of results JSONs "
                        "(2+ files; >2 = all vs the first, the baseline)")
    cp.add_argument("files", nargs="+",
                    help="baseline results JSON, then run(s) to compare")
    cp.add_argument("--json", action="store_true",
                    help="print machine-readable JSON to stdout")
    cp.add_argument("--checks", action="store_true",
                    help="also report per-check verdict flips")
    cp.add_argument("--best", action="store_true",
                    help="use the highest-scoring run as the baseline "
                         "instead of the first file")

    return p

def _split(s: str | None) -> list[str] | None:
    if not s:
        return None
    return [x.strip() for x in s.split(",") if x.strip()]


def cmd_list(args) -> int:
    try:
        tasks = load_dataset(args.dataset, version=args.dataset_version)
    except (DatasetError, CheckSpecError) as e:
        print(f"dataset invalid: {e}", file=sys.stderr)
        return 1
    cats = set(_split(args.categories) or [])
    rows = []
    for t in tasks:
        if cats and t.category not in cats:
            continue
        rows.append((t.id, t.category, t.difficulty, len(t.checks)))
    for tid, cat, diff, nchk in sorted(rows):
        print(f"{tid:<46} {cat:<16} d{diff} {nchk} checks")
    print(f"\n{len(rows)} task(s)")
    return 0


def cmd_validate(args) -> int:
    try:
        base = resolve_dataset_dir(args.dataset)
        tasks = load_dataset(base, version=args.dataset_version)
    except (DatasetError, CheckSpecError) as e:
        print(f"dataset invalid: {e}", file=sys.stderr)
        return 1
    cats = categories(tasks)
    print(f"dataset: {base} ({args.dataset_version})")
    print(f"sha256:  {dataset_digest(base, version=args.dataset_version)}")
    print(f"items:   {len(tasks)}")
    for c, n in cats.items():
        print(f"  {c:<16} {n}")
    print("checks:  " + ", ".join(check_types()))
    print("OK")
    return 0


def cmd_run(args) -> int:
    model = args.model or os.environ.get("KARNE_MODEL", "").strip()
    if not model:
        print("run: --model is required (or set KARNE_MODEL)", file=sys.stderr)
        return 2
    temperature = (
        args.temperature
        if args.temperature is not None
        else _env_float("KARNE_TEMPERATURE", 0.0)
    )
    timeout = (
        args.timeout
        if args.timeout is not None
        else _env_float("KARNE_TIMEOUT", 60.0)
    )
    cfg = RunConfig(
        model=model,
        base_url=args.base_url,
        api_key=args.api_key,
        dataset_path=args.dataset,
        version=args.dataset_version,
        categories=_split(args.categories),
        task_ids=_split(args.tasks),
        sample=args.sample,
        seed=args.seed,
        repeat=args.repeat,
        temperature=temperature,
        max_tokens=args.max_tokens,
        system_prompt=args.system_prompt or RunConfig.__dataclass_fields__[
            "system_prompt"
        ].default,
        concurrency=max(1, args.concurrency),
        rpm=args.rpm,
        cache_dir=None if args.cache.lower() in ("off", "none") else args.cache,
        timeout=timeout,
        max_retries=args.max_retries,
        label=args.label,
        judge_model=args.judge_model or os.environ.get("KARNE_JUDGE_MODEL"),
        judge_base_url=args.judge_base_url,
        judge_api_key=args.judge_api_key,
        judge_weight=args.judge_weight,
        judge_categories=(
            None
            if args.judge_categories is None
            else (
                ["*"]
                if args.judge_categories.strip().lower() == "all"
                else _split(args.judge_categories)
            )
        ),
        prompt_style=args.prompt_style,
        judge_runs=args.judge_runs,
    )
    if args.dry_run:
        from .runner import select_tasks

        try:
            tasks = load_dataset(cfg.dataset_path, version=cfg.version)
        except (DatasetError, CheckSpecError) as e:
            print(f"dataset invalid: {e}", file=sys.stderr)
            return 2
        sel = select_tasks(tasks, cfg)
        print(f"model:    {cfg.model}")
        print(f"style:    {cfg.prompt_style}")
        if cfg.judge_model:
            j = f"judge:    {cfg.judge_model} (w={cfg.judge_weight}"
            if cfg.judge_runs > 1:
                j += f", runs={cfg.judge_runs}"
            print(j + ")")
        print(f"dataset:  {cfg.version} · {len(tasks)} items total")
        n_tasks = len({t.id for t, _ in sel})
        print(f"selected: {n_tasks} task(s)"
              + (f" x{cfg.repeat} reps = {len(sel)} requests"
                 if cfg.repeat > 1 else ""))
        for t, rep in sel:
            if rep == 0:
                print(f"  - {t.id} (d{t.difficulty}, {len(t.checks)} checks)")
        # output estimate: honor explicit length requirements in count
        # checks; otherwise scale with task difficulty. Still a heuristic,
        # not a tokenizer — treat as an order-of-magnitude figure.
        def _est_tokens(t) -> int:
            best = 0
            for c in t.checks:
                if c.get("type") != "count":
                    continue
                unit = c.get("unit", "words")
                target = c.get("eq") or (
                    (c.get("min", 0) + c.get("max", c.get("min", 0))) / 2
                    if (c.get("min") is not None or c.get("max") is not None)
                    else 0
                )
                factor = {"words": 1.4, "sentences": 18,
                          "lines": 12, "chars": 0.3}.get(unit, 1.0)
                best = max(best, int(target * factor))
            if best:
                return min(cfg.max_tokens, max(best, 40))
            return min(cfg.max_tokens, 180 + t.difficulty * 110)

        chars = sum(
            len(t.prompt) + len(t.input or "") + len(cfg.system_prompt)
            for t, _ in sel
        )
        est_in = chars // 4

        est_out = sum(_est_tokens(t) for t, _ in sel)
        print(f"est. tokens: ~{est_in} in · ~{est_out} out "
              f"(heuristic: count-check targets or difficulty)")
        from .client import estimate_cost_usd

        cost = estimate_cost_usd(
            cfg.model,
            {"prompt_tokens": est_in, "completion_tokens": est_out},
        )
        if cost is not None:
            print(f"est. cost:   ~${cost:.4f}")
        print(f"fingerprint: {cfg.fingerprint()}")
        return 0

    try:
        results = run_eval(cfg)
    except (ClientError, DatasetError, CheckSpecError) as e:
        print(f"run failed: {e}", file=sys.stderr)
        return 2

    out = Path(args.out) if args.out else Path(
        "results"
    ) / f"karne-{cfg.model.replace('/', '-')}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    save_results(results, out)
    s = results["summary"]
    print(f"model:  {results['model']}")
    print(f"score:  {s['score'] * 100:.1f}%  ({s['n']} tasks, {s['errors']} errors)")
    if s.get("ci95"):
        print(f"        95% CI [{s['ci95'][0] * 100:.1f}%, "
              f"{s['ci95'][1] * 100:.1f}%]")
    for cat, cs in s["by_category"].items():
        print(f"  {cat:<16} {cs['score'] * 100:5.1f}%  n={cs['n']}")
    if s.get("n_rep_unstable"):
        print(f"unstable: {s['n_rep_unstable']} task(s) flip verdict "
              f"across reps: {', '.join(s['rep_unstable'][:6])}")
    if s.get("score_worst_rep") is not None:
        print(f"        worst/best rep "
              f"{s['score_worst_rep'] * 100:.1f}%–"
              f"{s['score_best_rep'] * 100:.1f}%")
    if s.get("est_cost_usd") is not None:
        print(f"cost:   ~${s['est_cost_usd']:.4f}")
    print(f"time:   {s['elapsed_ms'] / 1000:.1f}s  cache hits: {s['cache_hits']}")
    print(f"wrote:  {out}")
    if args.html is not None:
        hpath = Path(args.html) if args.html else out.with_suffix(".html")
        write_html(results, hpath)
        print(f"wrote:  {hpath}")
    if s["n"] and s["errors"] >= s["n"]:
        first = next(
            (t.get("error") for t in results.get("tasks", []) if t.get("error")),
            None,
        )
        print(
            "run failed: every request errored"
            + (f" (first error: {first})" if first else ""),
            file=sys.stderr,
        )
        return 2
    if s["errors"]:
        print(f"warning: {s['errors']} task(s) errored; their score counts as 0",
              file=sys.stderr)
    return 0

def _load_or_fail(paths, cmd: str):
    """Load results JSON files; print a one-line error instead of a traceback."""
    try:
        return [load_results(p) for p in paths]
    except FileNotFoundError as e:
        print(f"{cmd}: no such file: {e.filename}", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"{cmd}: not a results JSON file: {e}", file=sys.stderr)
    except OSError as e:
        print(f"{cmd}: {e}", file=sys.stderr)
    return None


def cmd_report(args) -> int:
    runs = _load_or_fail(args.results, "report")
    if runs is None:
        return 2
    if args.format == "md":
        from .report import render_markdown

        text = render_markdown(runs, title=args.title)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
            print(f"wrote: {args.out} ({len(runs)} run(s))")
        else:
            print(text, end="")
        return 0
    if not args.out:
        print("report: --out is required for --format html", file=sys.stderr)
        return 2
    write_html(runs, args.out, title=args.title)
    print(f"wrote: {args.out} ({len(runs)} run(s))")
    return 0


def cmd_compare(args) -> int:
    if len(args.files) == 1:
        print("compare: need at least 2 results files", file=sys.stderr)
        return 2
    runs = _load_or_fail(args.files, "compare")
    if runs is None:
        return 2
    if args.best:
        def _score(r: dict) -> float:
            v = r.get("summary", {}).get("score")
            return v if isinstance(v, (int, float)) else -1.0

        runs.sort(
            key=_score,
            reverse=True,
        )
    if len(runs) == 2:
        rep = compare_runs(runs[0], runs[1], include_checks=args.checks)
        print(
            json.dumps(rep, ensure_ascii=False, indent=2)
            if args.json
            else format_compare(rep)
        )
        return 0
    from .compare import compare_many, format_multi

    rep = compare_many(runs, include_checks=args.checks)
    print(
        json.dumps(rep, ensure_ascii=False, indent=2)
        if args.json
        else format_multi(rep)
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fn = {
        "list": cmd_list,
        "validate": cmd_validate,
        "run": cmd_run,
        "report": cmd_report,
        "compare": cmd_compare,
    }[args.cmd]
    try:
        return fn(args)
    except BrokenPipeError:
        # output piped into `head` etc.: exit quietly like other CLI tools
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0


if __name__ == "__main__":
    sys.exit(main())
