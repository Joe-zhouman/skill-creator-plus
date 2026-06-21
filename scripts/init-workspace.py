#!/usr/bin/env python3
"""init-workspace.py — Scaffold a test workspace for a skill.

Usage:
  init-workspace.py --skill-path <path> --evals <evals.json> [--iteration N] [--runs-per-config N]

Reads evals.json, creates the workspace directory tree, and writes
eval_metadata.json for each eval. The workspace is created inside the
skill at <skill>/tests/workspace/ (gitignored — local run state).

Example:
  init-workspace.py --skill-path skills/my-skill --evals skills/my-skill/tests/evals/evals.json
  init-workspace.py --skill-path skills/my-skill --evals skills/my-skill/tests/evals/evals.json --iteration 2 --runs-per-config 3
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


def _error_envelope(type_: str, subtype: str, message: str,
                    param: Optional[str] = None, hint: Optional[str] = None) -> dict:
    env = {"type": type_, "subtype": subtype, "message": message}
    if param is not None:
        env["param"] = param
    if hint is not None:
        env["hint"] = hint
    return env


def _grading_template() -> dict:
    """Empty grading.json skeleton. Grader subagent fills values; structure
    is fixed so field names can't drift from what aggregate_benchmark expects."""
    return {
        "expectations": [],
        "summary": {"passed": 0, "failed": 0, "total": 0, "pass_rate": 0.0},
        "execution_metrics": {
            "tool_calls": {},
            "total_tool_calls": 0,
            "total_steps": 0,
            "errors_encountered": 0,
            "output_chars": 0,
            "transcript_chars": 0,
        },
        "timing": {
            "executor_duration_seconds": 0,
            "grader_duration_seconds": 0,
            "total_duration_seconds": 0,
        },
        "claims": [],
        "user_notes_summary": {
            "uncertainties": [],
            "needs_review": [],
            "workarounds": [],
        },
    }


def init_workspace(skill_path: Path, evals_path: Path, iteration: int,
                   runs_per_config: int = 3) -> dict:
    """Create workspace directory tree and eval metadata files.

    Returns a result dict with created paths and counts.

    Raises ValueError with a structured message if evals.json is not
    parseable or has an unsupported shape. Callers should catch and
    convert to an error envelope.
    """
    try:
        evals_data = json.loads(evals_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(
            f"evals file is not valid JSON: {e}"
        ) from e

    # Accept both shapes:
    #   { "skill_name": "...", "evals": [...] }   ← gen-eval.py output
    #   [...]                                      ← bare array, simpler for hand-written
    if isinstance(evals_data, list):
        evals = evals_data
        skill_name = skill_path.name
    elif isinstance(evals_data, dict):
        if "evals" not in evals_data:
            raise ValueError(
                "evals file is a JSON object but has no 'evals' field. "
                "Expected either an array of eval objects, or an object "
                "like {\"skill_name\": \"...\", \"evals\": [...]}."
            )
        evals = evals_data["evals"]
        skill_name = evals_data.get("skill_name", skill_path.name)
    else:
        raise ValueError(
            f"evals file must be a JSON array or an object with an 'evals' array, "
            f"got {type(evals_data).__name__}"
        )

    if not isinstance(evals, list):
        raise ValueError(
            f"'evals' field must be a JSON array, got {type(evals).__name__}"
        )

    if not evals:
        raise ValueError(
            "evals file contains no eval entries — refusing to scaffold an empty "
            "workspace. Add at least one eval before running init-workspace."
        )

    workspace = skill_path / "tests" / "workspace"
    iter_dir = workspace / f"iteration-{iteration}"

    created_dirs = []
    created_files = []

    for ev in evals:
        eval_id = ev.get("id", 0)
        eval_dir = iter_dir / f"eval-{eval_id}"

        # Create run directories (run-M layout matches aggregate_benchmark.py)
        # and scaffold the per-run JSON templates so AGENTs fill values,
        # not structure.
        for config in ("with_skill", "without_skill"):
            for run_num in range(1, runs_per_config + 1):
                run_dir = eval_dir / config / f"run-{run_num}"
                outputs_dir = run_dir / "outputs"
                outputs_dir.mkdir(parents=True, exist_ok=True)
                created_dirs.append(str(outputs_dir))

                # timing.json — only the 2 fields aggregate_benchmark reads.
                # AGENT fills these from the subagent task notification.
                timing_path = run_dir / "timing.json"
                timing_path.write_text(
                    json.dumps({"total_tokens": 0, "total_duration_seconds": None},
                               indent=2) + "\n",
                    encoding="utf-8",
                )
                created_files.append(str(timing_path))

                # grading.json — full skeleton, grader subagent fills values.
                grading_path = run_dir / "grading.json"
                grading_path.write_text(
                    json.dumps(_grading_template(), indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                created_files.append(str(grading_path))

        # Write eval_metadata.json
        metadata = {
            "eval_id": eval_id,
            "eval_name": ev.get("prompt", "")[:60].split("\n")[0].strip() or f"eval-{eval_id}",
            "prompt": ev.get("prompt", ""),
            "expectations": [],
        }
        meta_path = eval_dir / "eval_metadata.json"
        meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
        created_files.append(str(meta_path))

    return {
        "ok": True,
        "workspace": str(workspace),
        "iteration_dir": str(iter_dir),
        "eval_count": len(evals),
        "runs_per_config": runs_per_config,
        "dirs_created": len(created_dirs),
        "files_created": len(created_files),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a test workspace for a skill")
    parser.add_argument("--skill-path", type=Path, required=True,
                        help="Path to the skill directory")
    parser.add_argument("--evals", type=Path, required=True,
                        help="Path to tests/evals/evals.json")
    parser.add_argument("--iteration", type=int, default=1,
                        help="Iteration number (default: 1)")
    parser.add_argument("--runs-per-config", type=int, default=3,
                        help="Number of runs per configuration (default: 3)")
    parser.add_argument("--format", choices=["json", "pretty"], default=None,
                        help="Output format (default: json in pipe, pretty on TTY)")
    args = parser.parse_args()

    fmt = args.format or ("json" if not sys.stdout.isatty() else "pretty")

    skill_path = args.skill_path.resolve()
    evals_path = args.evals.resolve()

    if not skill_path.is_dir():
        err = _error_envelope(
            "validation_error", "invalid_argument",
            "skill-path must be a directory",
            param="--skill-path",
            hint="pass the absolute path to a skill directory, e.g. /home/me/skills/my-skill",
        )
        print(json.dumps(err), file=sys.stderr)
        return 2

    if not evals_path.is_file():
        err = _error_envelope(
            "not_found", "file_missing",
            f"evals file not found: {evals_path}",
            param="--evals",
            hint="run gen-eval.py first, e.g. gen-eval.py my-skill tests/evals/evals.json",
        )
        print(json.dumps(err), file=sys.stderr)
        return 2

    if args.runs_per_config < 1:
        err = _error_envelope(
            "validation_error", "invalid_argument",
            "runs-per-config must be >= 1",
            param="--runs-per-config",
            hint="use 1 for a single run, 3 (default) for statistical aggregation",
        )
        print(json.dumps(err), file=sys.stderr)
        return 2

    try:
        result = init_workspace(skill_path, evals_path, args.iteration, args.runs_per_config)
    except ValueError as e:
        err = _error_envelope(
            "validation_error", "invalid_evals_file",
            str(e),
            param="--evals",
            hint="expected either a JSON array of eval objects, "
                 "or an object like {\"skill_name\": \"...\", \"evals\": [...]}",
        )
        print(json.dumps(err), file=sys.stderr)
        return 2
    except OSError as e:
        err = _error_envelope(
            "runtime_error", "io_error",
            f"failed to read evals file: {e}",
            param="--evals",
        )
        print(json.dumps(err), file=sys.stderr)
        return 1

    if fmt == "pretty":
        print(f"  workspace: {result['workspace']}")
        print(f"  iteration: {result['iteration_dir']}")
        print(f"  {result['eval_count']} evals × {result['runs_per_config']} runs = {result['eval_count'] * result['runs_per_config']} subagent tasks per side ({result['eval_count'] * result['runs_per_config'] * 2} total across both configs)")
        print(f"  {result['dirs_created']} dirs, {result['files_created']} metadata files")
        print("  OK")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
