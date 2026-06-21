#!/usr/bin/env python3
"""aggregate_benchmark.py — Aggregate run results into benchmark summary statistics.

Usage:
  aggregate_benchmark.py <benchmark_dir>              # auto: pretty (TTY) or json (pipe)
  aggregate_benchmark.py <benchmark_dir> --format json
  aggregate_benchmark.py <benchmark_dir> --skill-name my-skill
  aggregate_benchmark.py <benchmark_dir> -o results/benchmark.json

Reads grading.json files from run directories and produces:
- benchmark.json with runs, run_summary, and metadata
- benchmark.md with human-readable summary table

Two directory layouts supported:
  Workspace layout:  <dir>/eval-N/{with_skill,without_skill}/run-M/grading.json
  Legacy layout:     <dir>/runs/eval-N/{with_skill,without_skill}/run-M/grading.json
"""

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def _error_envelope(type_: str, subtype: str, message: str,
                    param: Optional[str] = None, hint: Optional[str] = None) -> dict:
    env = {"type": type_, "subtype": subtype, "message": message}
    if param is not None:
        env["param"] = param
    if hint is not None:
        env["hint"] = hint
    return env


def _log(msg: str) -> None:
    """Print to stderr — never pollute stdout data channel."""
    print(msg, file=sys.stderr)


def calculate_stats(values: List[float]) -> dict:
    """Calculate mean, stddev, min, max for a list of values.

    None values (from scaffolded-but-unfilled timing.json templates) are
    filtered out before computing stats.
    """
    clean = [v for v in values if v is not None]
    if not clean:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0}

    n = len(clean)
    mean = sum(clean) / n

    if n > 1:
        variance = sum((x - mean) ** 2 for x in clean) / (n - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0

    return {
        "mean": round(mean, 4),
        "stddev": round(stddev, 4),
        "min": round(min(clean), 4),
        "max": round(max(clean), 4)
    }


def load_run_results(benchmark_dir: Path) -> dict:
    """
    Load all run results from a benchmark directory.

    Returns dict keyed by config name, each containing a list of run results.
    """
    runs_dir = benchmark_dir / "runs"
    if runs_dir.exists():
        search_dir = runs_dir
    elif list(benchmark_dir.glob("eval-*")):
        search_dir = benchmark_dir
    else:
        _log(f"Warning: no eval directories found in {benchmark_dir}")
        return {}

    results: Dict[str, List[dict]] = {}

    for eval_idx, eval_dir in enumerate(sorted(search_dir.glob("eval-*"))):
        metadata_path = eval_dir / "eval_metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path) as mf:
                    eval_id = json.load(mf).get("eval_id", eval_idx)
            except (json.JSONDecodeError, OSError):
                eval_id = eval_idx
        else:
            try:
                eval_id = int(eval_dir.name.split("-")[1])
            except ValueError:
                eval_id = eval_idx

        for config_dir in sorted(eval_dir.iterdir()):
            if not config_dir.is_dir():
                continue
            if not list(config_dir.glob("run-*")):
                continue
            config = config_dir.name
            if config not in results:
                results[config] = []

            for run_dir in sorted(config_dir.glob("run-*")):
                run_number = int(run_dir.name.split("-")[1])
                grading_file = run_dir / "grading.json"

                if not grading_file.exists():
                    _log(f"Warning: grading.json not found in {run_dir}")
                    continue

                try:
                    with open(grading_file) as f:
                        grading = json.load(f)
                except json.JSONDecodeError as e:
                    _log(f"Warning: invalid JSON in {grading_file}: {e}")
                    continue

                # Compute pass/total from expectations directly. We don't trust
                # grading.summary because grader subagents frequently omit it
                # (they fill expectations[] but not the summary aggregate). If
                # summary IS present and well-formed, prefer it — but fall back
                # to recomputing from expectations when it's missing/empty.
                expectations = grading.get("expectations", []) or []
                passed_from_exps = sum(1 for e in expectations if e.get("passed") is True)
                total_from_exps = len(expectations)

                summary = grading.get("summary") or {}
                if isinstance(summary, dict) and summary.get("total"):
                    # Summary is populated and non-zero — trust it.
                    passed = summary.get("passed", 0)
                    failed = summary.get("failed", 0)
                    total = summary.get("total", 0)
                    pass_rate = summary.get("pass_rate", passed / total if total else 0.0)
                else:
                    # Summary missing or empty — recompute from expectations.
                    passed = passed_from_exps
                    total = total_from_exps
                    failed = total - passed
                    pass_rate = passed / total if total else 0.0

                result = {
                    "eval_id": eval_id,
                    "run_number": run_number,
                    "pass_rate": pass_rate,
                    "passed": passed,
                    "failed": failed,
                    "total": total,
                }

                timing = grading.get("timing", {})
                result["time_seconds"] = timing.get("total_duration_seconds", 0.0)
                timing_file = run_dir / "timing.json"
                if result["time_seconds"] == 0.0 and timing_file.exists():
                    try:
                        with open(timing_file) as tf:
                            timing_data = json.load(tf)
                        result["time_seconds"] = timing_data.get("total_duration_seconds", 0.0)
                        result["tokens"] = timing_data.get("total_tokens", 0)
                    except json.JSONDecodeError:
                        pass

                metrics = grading.get("execution_metrics", {})
                result["tool_calls"] = metrics.get("total_tool_calls", 0)
                if not result.get("tokens"):
                    result["tokens"] = metrics.get("output_chars", 0)
                result["errors"] = metrics.get("errors_encountered", 0)

                raw_expectations = grading.get("expectations", [])
                for exp in raw_expectations:
                    if "text" not in exp or "passed" not in exp:
                        _log(f"Warning: expectation in {grading_file} missing required fields: {exp}")
                result["expectations"] = raw_expectations

                notes_summary = grading.get("user_notes_summary", {})
                notes = []
                notes.extend(notes_summary.get("uncertainties", []))
                notes.extend(notes_summary.get("needs_review", []))
                notes.extend(notes_summary.get("workarounds", []))
                result["notes"] = notes

                results[config].append(result)

    return results


def aggregate_results(results: dict) -> dict:
    """
    Aggregate run results into summary statistics.

    Returns run_summary with stats for each configuration and delta.
    """
    run_summary = {}
    configs = list(results.keys())

    for config in configs:
        runs = results.get(config, [])

        if not runs:
            run_summary[config] = {
                "pass_rate": {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0},
                "time_seconds": {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0},
                "tokens": {"mean": 0, "stddev": 0, "min": 0, "max": 0}
            }
            continue

        pass_rates = [r["pass_rate"] for r in runs]
        times = [r["time_seconds"] for r in runs]
        tokens_list = [r.get("tokens", 0) for r in runs]

        run_summary[config] = {
            "pass_rate": calculate_stats(pass_rates),
            "time_seconds": calculate_stats(times),
            "tokens": calculate_stats(tokens_list)
        }

    if len(configs) >= 2:
        primary = run_summary.get(configs[0], {})
        baseline = run_summary.get(configs[1], {})
    else:
        primary = run_summary.get(configs[0], {}) if configs else {}
        baseline = {}

    delta_pass_rate = primary.get("pass_rate", {}).get("mean", 0) - baseline.get("pass_rate", {}).get("mean", 0)
    delta_time = primary.get("time_seconds", {}).get("mean", 0) - baseline.get("time_seconds", {}).get("mean", 0)
    delta_tokens = primary.get("tokens", {}).get("mean", 0) - baseline.get("tokens", {}).get("mean", 0)

    run_summary["delta"] = {
        "pass_rate": f"{delta_pass_rate:+.2f}",
        "time_seconds": f"{delta_time:+.1f}",
        "tokens": f"{delta_tokens:+.0f}"
    }

    return run_summary


def generate_benchmark(benchmark_dir: Path, skill_name: str = "", skill_path: str = "") -> dict:
    """Generate complete benchmark.json from run results."""
    results = load_run_results(benchmark_dir)
    run_summary = aggregate_results(results)

    runs = []
    for config in results:
        for result in results[config]:
            runs.append({
                "eval_id": result["eval_id"],
                "configuration": config,
                "run_number": result["run_number"],
                "result": {
                    "pass_rate": result["pass_rate"],
                    "passed": result["passed"],
                    "failed": result["failed"],
                    "total": result["total"],
                    "time_seconds": result["time_seconds"],
                    "tokens": result.get("tokens", 0),
                    "tool_calls": result.get("tool_calls", 0),
                    "errors": result.get("errors", 0)
                },
                "expectations": result["expectations"],
                "notes": result["notes"]
            })

    eval_ids = sorted(set(
        r["eval_id"]
        for config in results.values()
        for r in config
    ))

    # Count actual runs per config (may vary across evals; take the max)
    runs_per_config = 0
    for config in results.values():
        for r in config:
            runs_per_config = max(runs_per_config, r["run_number"])

    benchmark = {
        "metadata": {
            "skill_name": skill_name or "<skill-name>",
            "skill_path": skill_path or "<path/to/skill>",
            "executor_model": "<model-name>",
            "analyzer_model": "<model-name>",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evals_run": eval_ids,
            "runs_per_configuration": runs_per_config
        },
        "runs": runs,
        "run_summary": run_summary,
        "notes": []
    }

    return benchmark


def generate_markdown(benchmark: dict, benchmark_dir: Optional[Path] = None) -> str:
    """Generate human-readable benchmark.md from benchmark data.

    If benchmark_dir is provided, include a per-eval section listing output file
    paths so the reviewer can navigate to outputs without an inline viewer.
    """
    metadata = benchmark["metadata"]
    run_summary = benchmark["run_summary"]

    configs = [k for k in run_summary if k != "delta"]
    config_a = configs[0] if len(configs) >= 1 else "config_a"
    config_b = configs[1] if len(configs) >= 2 else "config_b"
    label_a = config_a.replace("_", " ").title()
    label_b = config_b.replace("_", " ").title()

    lines = [
        f"# Skill Benchmark: {metadata['skill_name']}",
        "",
        f"**Model**: {metadata['executor_model']}",
        f"**Date**: {metadata['timestamp']}",
        f"**Evals**: {', '.join(map(str, metadata['evals_run']))} ({metadata['runs_per_configuration']} runs each per configuration)",
        "",
        "## Summary",
        "",
        f"| Metric | {label_a} | {label_b} | Delta |",
        "|--------|------------|---------------|-------|",
    ]

    a_summary = run_summary.get(config_a, {})
    b_summary = run_summary.get(config_b, {})
    delta = run_summary.get("delta", {})

    a_pr = a_summary.get("pass_rate", {})
    b_pr = b_summary.get("pass_rate", {})
    lines.append(f"| Pass Rate | {a_pr.get('mean', 0)*100:.0f}% ± {a_pr.get('stddev', 0)*100:.0f}% | {b_pr.get('mean', 0)*100:.0f}% ± {b_pr.get('stddev', 0)*100:.0f}% | {delta.get('pass_rate', '—')} |")

    a_time = a_summary.get("time_seconds", {})
    b_time = b_summary.get("time_seconds", {})
    lines.append(f"| Time | {a_time.get('mean', 0):.1f}s ± {a_time.get('stddev', 0):.1f}s | {b_time.get('mean', 0):.1f}s ± {b_time.get('stddev', 0):.1f}s | {delta.get('time_seconds', '—')}s |")

    a_tokens = a_summary.get("tokens", {})
    b_tokens = b_summary.get("tokens", {})
    lines.append(f"| Tokens | {a_tokens.get('mean', 0):.0f} ± {a_tokens.get('stddev', 0):.0f} | {b_tokens.get('mean', 0):.0f} ± {b_tokens.get('stddev', 0):.0f} | {delta.get('tokens', '—')} |")

    # Per-eval outputs section — lets the reviewer open output files directly
    # from the MD, replacing the viewer's inline preview.
    if benchmark_dir is not None:
        eval_ids = sorted(metadata.get("evals_run", []))
        if eval_ids:
            lines.extend([
                "",
                "## Per-eval outputs",
                "",
                "Open these paths to review each run's output. Use them during the",
                "Step 4 conversation walk-through.",
                "",
            ])
            for eval_id in eval_ids:
                eval_dir = benchmark_dir / f"eval-{eval_id}"
                if not eval_dir.is_dir():
                    continue
                lines.append(f"### eval-{eval_id}")
                lines.append("")
                for config_dir in sorted(eval_dir.iterdir()):
                    if not config_dir.is_dir():
                        continue
                    config_label = config_dir.name.replace("_", " ").title()
                    lines.append(f"**{config_label}**:")
                    lines.append("")
                    for run_dir in sorted(config_dir.glob("run-*")):
                        outputs_dir = run_dir / "outputs"
                        rel = run_dir.relative_to(benchmark_dir)
                        if outputs_dir.is_dir():
                            files = sorted(f.name for f in outputs_dir.iterdir() if f.is_file())
                            if files:
                                file_list = ", ".join(files)
                                lines.append(f"- `{rel}/outputs/` — {file_list}")
                            else:
                                lines.append(f"- `{rel}/outputs/` — (empty)")
                        else:
                            lines.append(f"- `{rel}/` — (no outputs dir)")
                    lines.append("")

    if benchmark.get("notes"):
        lines.extend([
            "## Notes",
            ""
        ])
        for note in benchmark["notes"]:
            lines.append(f"- {note}")

    return "\n".join(lines)


def format_pretty(benchmark: dict, output_json: Path, output_md: Path) -> str:
    """Format a human-readable summary for TTY output."""
    run_summary = benchmark["run_summary"]
    configs = [k for k in run_summary if k != "delta"]
    delta = run_summary.get("delta", {})

    lines = [
        f"  wrote: {output_json}",
        f"  wrote: {output_md}",
        "",
    ]

    for config in configs:
        pr = run_summary[config]["pass_rate"]["mean"]
        label = config.replace("_", " ").title()
        lines.append(f"  {label}: {pr*100:.1f}% pass rate")

    lines.append(f"  Delta: {delta.get('pass_rate', '—')}")
    lines.append("  OK")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate benchmark run results into summary statistics"
    )
    parser.add_argument("benchmark_dir", type=Path,
                        help="Path to the benchmark directory")
    parser.add_argument("--skill-name", default="",
                        help="Name of the skill being benchmarked")
    parser.add_argument("--skill-path", default="",
                        help="Path to the skill being benchmarked")
    parser.add_argument("--output", "-o", type=Path,
                        help="Output path for benchmark.json (default: <benchmark_dir>/benchmark.json)")
    parser.add_argument("--format", choices=["json", "pretty"], default=None,
                        help="Output format (default: json in pipe, pretty on TTY)")
    args = parser.parse_args()

    fmt = args.format or ("json" if not sys.stdout.isatty() else "pretty")
    benchmark_dir = args.benchmark_dir.resolve()

    if not benchmark_dir.is_dir():
        err = _error_envelope(
            "not_found", "dir_missing",
            f"benchmark directory not found: {benchmark_dir}",
            param="benchmark_dir",
            hint="pass the path to the directory containing eval-N/ subdirectories",
        )
        print(json.dumps(err), file=sys.stderr)
        return 2

    benchmark = generate_benchmark(benchmark_dir, args.skill_name, args.skill_path)

    output_json = args.output or (benchmark_dir / "benchmark.json")
    output_md = output_json.with_suffix(".md")

    output_json.write_text(json.dumps(benchmark, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(generate_markdown(benchmark, benchmark_dir) + "\n", encoding="utf-8")

    if fmt == "json":
        result = {
            "ok": True,
            "wrote_json": str(output_json),
            "wrote_md": str(output_md),
            "run_count": len(benchmark["runs"]),
            "configs": [k for k in benchmark["run_summary"] if k != "delta"],
            "delta": benchmark["run_summary"].get("delta", {}),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_pretty(benchmark, output_json, output_md))

    return 0


if __name__ == "__main__":
    sys.exit(main())
