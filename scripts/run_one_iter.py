#!/usr/bin/env python3
"""run_one_iter.py — Run one round of trigger testing for skill description optimization.

Usage:
  run_one_iter.py --eval-set <trigger-evals.json> --skill-path <skill-dir> [options]

Reads a trigger eval set (list of {query, should_trigger}), runs each query
against the skill's current description, and writes per-iteration Markdown +
JSON reports. Designed for AGENT-orchestrated iteration: the AGENT runs this,
reads the Markdown, asks the human whether to continue, then either edits the
description or calls improve_description() (internal library) before the next
round.

Outputs (written to --output-dir, default: <skill-path>/description-optimization/):
  iter-N.md    — human-readable report (description, score, per-query table)
  iter-N.json  — machine-readable (same data, for AGENT to parse pass rate)

stdout: short JSON summary ({ok, iter, md_path, json_path, pass_rate, ...}).
stderr: progress (one line per query as it completes).

Exit codes:
  0 — round completed
  1 — evaluation produced no results (shouldn't happen; defensive)
  2 — input error (missing file, bad JSON, bad args) — emits error envelope
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from scripts.run_eval import find_project_root, run_eval
from scripts.utils import parse_skill_md


def _error_envelope(type_: str, subtype: str, message: str,
                    param: Optional[str] = None, hint: Optional[str] = None) -> dict:
    env = {"type": type_, "subtype": subtype, "message": message}
    if param is not None:
        env["param"] = param
    if hint is not None:
        env["hint"] = hint
    return env


def _fail(type_: str, subtype: str, message: str, exit_code: int = 2,
          param: Optional[str] = None, hint: Optional[str] = None) -> int:
    print(json.dumps(_error_envelope(type_, subtype, message, param=param, hint=hint)),
          file=sys.stderr)
    return exit_code


def render_markdown(iter_num: int, skill_name: str, description: str,
                    results: list, summary: dict) -> str:
    """Render the per-iteration Markdown report."""
    total = summary["total"]
    passed = summary["passed"]

    should_trigger_items = [r for r in results if r["should_trigger"]]
    should_not_items = [r for r in results if not r["should_trigger"]]
    st_pass = sum(1 for r in should_trigger_items if r["pass"])
    sn_pass = sum(1 for r in should_not_items if r["pass"])

    lines = [
        f"# Iteration {iter_num} — {skill_name}",
        "",
        "**Current description:**",
        "",
        f"> {description}",
        "",
        "## Summary",
        "",
        f"- **Pass rate:** {passed}/{total} queries ({passed/total*100:.0f}%)" if total else "- **Pass rate:** (no queries)",
        f"- **Should-trigger:** {st_pass}/{len(should_trigger_items)} correctly triggered",
        f"- **Should-NOT-trigger:** {sn_pass}/{len(should_not_items)} correctly stayed silent",
        "",
        "## Per-query results",
        "",
        "| Pass | Query | Expected | Triggered |",
        "|------|-------|----------|-----------|",
    ]

    for r in results:
        mark = "✓" if r["pass"] else "✗"
        expected = "trigger" if r["should_trigger"] else "silent"
        triggered = f"{r['triggers']}/{r['runs']}"
        query = r["query"].replace("|", "\\|").replace("\n", " ")
        if len(query) > 80:
            query = query[:77] + "..."
        lines.append(f"| {mark} | {query} | {expected} | {triggered} |")

    lines.extend([
        "",
        "## Failing queries",
        "",
    ])

    failures = [r for r in results if not r["pass"]]
    if not failures:
        lines.append("(none — all queries passed this round)")
    else:
        for r in failures:
            kind = "did NOT trigger (should have)" if r["should_trigger"] else "triggered (should NOT have)"
            lines.append(f"- **{kind}** — trigger rate {r['triggers']}/{r['runs']}")
            lines.append(f"  > {r['query']}")
            lines.append("")

    return "\n".join(lines) + "\n"


def run_one_iter(
    eval_set: list,
    skill_name: str,
    description: str,
    iteration: int,
    output_dir: Path,
    runs_per_query: int = 3,
    num_workers: int = 10,
    timeout: int = 30,
    trigger_threshold: float = 0.5,
    model: Optional[str] = None,
) -> dict:
    """Run one iteration. Returns result dict with paths and summary."""
    project_root = find_project_root()

    output = run_eval(
        eval_set=eval_set,
        skill_name=skill_name,
        description=description,
        num_workers=num_workers,
        timeout=timeout,
        project_root=project_root,
        runs_per_query=runs_per_query,
        trigger_threshold=trigger_threshold,
        model=model,
    )

    results = output["results"]
    summary = output["summary"]

    md_path = output_dir / f"iter-{iteration}.md"
    json_path = output_dir / f"iter-{iteration}.json"

    md_content = render_markdown(iteration, skill_name, description, results, summary)
    md_path.write_text(md_content, encoding="utf-8")

    json_payload = {
        "iteration": iteration,
        "skill_name": skill_name,
        "description": description,
        "summary": summary,
        "results": results,
    }
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")

    return {
        "ok": True,
        "iteration": iteration,
        "md_path": str(md_path),
        "json_path": str(json_path),
        "pass_rate": summary["passed"] / summary["total"] if summary["total"] else 0.0,
        "passed": summary["passed"],
        "total": summary["total"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one round of trigger testing for description optimization",
    )
    parser.add_argument("--eval-set", type=Path, required=True,
                        help="Path to trigger eval set JSON (list of {query, should_trigger})")
    parser.add_argument("--skill-path", type=Path, required=True,
                        help="Path to the skill directory")
    parser.add_argument("--iteration", type=int, default=1,
                        help="Iteration number (default: 1)")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Where to write iter-N.md/json (default: <skill-path>/description-optimization/)")
    parser.add_argument("--description", default=None,
                        help="Override description (default: read from SKILL.md frontmatter)")
    parser.add_argument("--runs-per-query", type=int, default=3,
                        help="Runs per query for trigger rate (default: 3)")
    parser.add_argument("--num-workers", type=int, default=10,
                        help="Parallel workers (default: 10)")
    parser.add_argument("--timeout", type=int, default=30,
                        help="Per-query timeout in seconds (default: 30)")
    parser.add_argument("--trigger-threshold", type=float, default=0.5,
                        help="Trigger rate above which a query counts as triggered (default: 0.5)")
    parser.add_argument("--model", default=None,
                        help="Model for claude -p (default: user's configured model)")
    parser.add_argument("--format", choices=["json", "pretty"], default=None,
                        help="Output format (default: json in pipe, pretty on TTY)")
    args = parser.parse_args()

    fmt = args.format or ("json" if not sys.stdout.isatty() else "pretty")

    # Validate eval-set
    eval_set_path = args.eval_set.resolve()
    if not eval_set_path.is_file():
        return _fail(
            "not_found", "file_missing",
            f"eval-set file not found: {eval_set_path}",
            param="--eval-set",
            hint="path must point to a JSON file of {query, should_trigger} items",
        )
    try:
        eval_set = json.loads(eval_set_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return _fail(
            "validation_error", "invalid_json",
            f"eval-set file is not valid JSON: {e}",
            param="--eval-set",
            hint="check for trailing commas, unquoted keys, or encoding issues",
        )
    if not isinstance(eval_set, list):
        return _fail(
            "validation_error", "invalid_structure",
            f"eval-set must be a JSON array, got {type(eval_set).__name__}",
            param="--eval-set",
            hint="top-level should be [{query, should_trigger}, ...]",
        )

    # Validate skill-path
    skill_path = args.skill_path.resolve()
    if not skill_path.is_dir():
        return _fail(
            "not_found", "dir_missing",
            f"skill directory not found: {skill_path}",
            param="--skill-path",
            hint="pass the absolute path to a skill directory containing SKILL.md",
        )
    skill_md = skill_path / "SKILL.md"
    if not skill_md.is_file():
        return _fail(
            "not_found", "file_missing",
            f"no SKILL.md in skill directory: {skill_path}",
            param="--skill-path",
            hint="every skill must have a SKILL.md at its root",
        )

    try:
        name, _, _ = parse_skill_md(skill_path)
    except ValueError as e:
        return _fail(
            "validation_error", "invalid_frontmatter",
            f"SKILL.md frontmatter is invalid: {e}",
            param="--skill-path",
            hint="SKILL.md must start with '---' and close with a matching '---'",
        )

    # Description: explicit override or read from frontmatter
    if args.description is not None:
        description = args.description
        skill_name = name
    else:
        # parse_skill_md returns (name, description, content)
        _, description, _ = parse_skill_md(skill_path)
        skill_name = name
        if not description.strip():
            return _fail(
                "validation_error", "missing_field",
                "SKILL.md has no description in frontmatter",
                param="--skill-path",
                hint="add a description: field to SKILL.md frontmatter, or pass --description",
            )

    if args.runs_per_query < 1:
        return _fail(
            "validation_error", "invalid_argument",
            "runs-per-query must be >= 1",
            param="--runs-per-query",
            hint="use 1 for a quick check, 3 (default) for a stable trigger rate",
        )

    # Output dir
    output_dir = args.output_dir or (skill_path.parent / f"{skill_path.name}-description-optimization")
    output_dir.mkdir(parents=True, exist_ok=True)

    if fmt == "pretty":
        print(f"  skill: {skill_name}", file=sys.stderr)
        print(f"  iter:  {args.iteration}", file=sys.stderr)
        print(f"  queries: {len(eval_set)} × {args.runs_per_query} runs = {len(eval_set) * args.runs_per_query} claude -p calls", file=sys.stderr)
        print(f"  output: {output_dir}", file=sys.stderr)

    result = run_one_iter(
        eval_set=eval_set,
        skill_name=skill_name,
        description=description,
        iteration=args.iteration,
        output_dir=output_dir,
        runs_per_query=args.runs_per_query,
        num_workers=args.num_workers,
        timeout=args.timeout,
        trigger_threshold=args.trigger_threshold,
        model=args.model,
    )

    if fmt == "pretty":
        print(f"  pass rate: {result['passed']}/{result['total']}", file=sys.stderr)
        print(f"  md:   {result['md_path']}", file=sys.stderr)
        print(f"  json: {result['json_path']}", file=sys.stderr)
        print(f"\n  Read the Markdown, then ask the human whether to continue.", file=sys.stderr)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
