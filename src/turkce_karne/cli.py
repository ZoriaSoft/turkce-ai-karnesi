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
from .report import render_html, runs_from_files, write_html
from .runner import RunConfig, load_results, run_eval, save_results
from .compare import compare_runs, format_compare


def _env_or(default=None):
    import os

    return default


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
    rp.add_argument("--model", required=True,
                    help="model name (or KARNE_MODEL)")
    rp.add_argument("--dataset", help="dataset dir")
    rp.add_argument("--dataset-version", default="v1")
    rp.add_argument("--tasks", help="comma-separated task ids")
    rp.add_argument("--categories", help="comma-separated categories")
    rp.add_argument("--sample", type=int, help="sample N tasks (seeded)")
    rp.add_argument("--seed", type=int, default=42)
    rp.add_argument("--repeat", type=int, default=1,
                    help="repeat each task N times")
    rp.add_argument("--temperature", type=float, default=0.0)
    rp.add_argument("--max-tokens", type=int, default=2048)
    rp.add_argument("--concurrency", type=int, default=4)
    rp.add_argument("--rpm", type=float, help="requests per minute cap")
    rp.add_argument("--timeout", type=float, default=60.0)
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

    hp = sub.add_parser("report", help="Render results JSON(s) to HTML")
    hp.add_argument("results", nargs="+", help="results JSON file(s)")
    hp.add_argument("--out", required=True, help="output HTML path")
    hp.add_argument("--title", help="report title")

    cp = sub.add_parser("compare", help="Paired diff of two results JSONs")
    cp.add_argument("a", help="baseline results JSON")
    cp.add_argument("b", help="new results JSON")
    cp.add_argument("--json", action="store_true",
                    help="print machine-readable JSON to stdout")

    return p

def _split(s: str | None) -> list[str] | None:
    if not s:
        return None
    return [x.strip() for x in s.split(",") if x.strip()]


def cmd_list(args) -> int:
    tasks = load_dataset(args.dataset, version=args.dataset_version)
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
    cfg = RunConfig(
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        dataset_path=args.dataset,
        version=args.dataset_version,
        categories=_split(args.categories),
        task_ids=_split(args.tasks),
        sample=args.sample,
        seed=args.seed,
        repeat=args.repeat,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        system_prompt=args.system_prompt or RunConfig.__dataclass_fields__[
            "system_prompt"
        ].default,
        concurrency=max(1, args.concurrency),
        rpm=args.rpm,
        cache_dir=None if args.cache.lower() in ("off", "none") else args.cache,
        timeout=args.timeout,
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
    )
    if args.dry_run:
        from .runner import select_tasks

        tasks = load_dataset(cfg.dataset_path, version=cfg.version)
        sel = select_tasks(tasks, cfg)
        print(f"model:    {cfg.model}")
        print(f"style:    {cfg.prompt_style}")
        if cfg.judge_model:
            print(f"judge:    {cfg.judge_model} (w={cfg.judge_weight})")
        print(f"dataset:  {cfg.version} · {len(tasks)} items total")
        print(f"selected: {len(sel)} task(s)")
        for t in sel:
            print(f"  - {t.id} (d{t.difficulty}, {len(t.checks)} checks)")
        # crude token estimate: ~4 chars/token for Turkish text in+out;
        # output assumed at a typical few-hundred-token completion
        chars = sum(
            len(t.prompt) + len(t.input or "") + len(cfg.system_prompt)
            for t in sel
        )
        est_in = chars // 4
        est_out = min(cfg.max_tokens, 400) * len(sel)
        print(f"est. tokens: ~{est_in} in · ~{est_out} out "
              f"(rough 4-chars/token heuristic)")
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
    for cat, cs in s["by_category"].items():
        print(f"  {cat:<16} {cs['score'] * 100:5.1f}%  n={cs['n']}")
    if s.get("est_cost_usd") is not None:
        print(f"cost:   ~${s['est_cost_usd']:.4f}")
    print(f"time:   {s['elapsed_ms'] / 1000:.1f}s  cache hits: {s['cache_hits']}")
    print(f"wrote:  {out}")
    if args.html is not None:
        hpath = Path(args.html) if args.html else out.with_suffix(".html")
        write_html(results, hpath)
        print(f"wrote:  {hpath}")
    return 0

def cmd_report(args) -> int:
    runs = runs_from_files(args.results)
    write_html(runs, args.out, title=args.title)
    print(f"wrote: {args.out} ({len(runs)} run(s))")
    return 0


def cmd_compare(args) -> int:
    rep = compare_runs(load_results(args.a), load_results(args.b))
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(format_compare(rep))
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
    return fn(args)


if __name__ == "__main__":
    sys.exit(main())
