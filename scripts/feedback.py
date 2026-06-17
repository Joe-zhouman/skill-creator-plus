#!/usr/bin/env python3
"""feedback.py — Own the feedback.json format for benchmark eval iterations.

Usage:
  feedback.py add --iteration-dir <dir> --run-id <id> --feedback "<text>"
  feedback.py show --iteration-dir <dir> [--format json|pretty]

feedback.json lives at <iteration-dir>/feedback.json and collects per-run human
reviews during the Step 4 conversation walk-through. The AGENT calls `add` once
per run as the user gives feedback, and `show` at the start of the next
iteration to surface previous comments.

Schema:
  {
    "iteration": 2,             # parsed from dir name (iteration-N), else null
    "reviews": [
      {"run_id": "eval-1/with_skill/run-1", "feedback": "...", "timestamp": "..."}
    ]
  }

`add` is idempotent per run_id: calling it twice with the same run_id updates
the existing entry (refreshing timestamp) rather than appending.

Exit codes:
  0 — ok (add wrote file; show printed reviews, possibly empty)
  2 — input error (missing dir, corrupt JSON, missing required arg)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
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


def _fail(type_: str, subtype: str, message: str, exit_code: int = 2,
          param: Optional[str] = None, hint: Optional[str] = None) -> int:
    print(json.dumps(_error_envelope(type_, subtype, message, param=param, hint=hint)),
          file=sys.stderr)
    return exit_code


def _feedback_path(iteration_dir: Path) -> Path:
    return iteration_dir / "feedback.json"


def _parse_iteration(iteration_dir: Path) -> Optional[int]:
    """Extract N from a directory named 'iteration-N'. None if no match."""
    m = re.match(r"iteration-(\d+)$", iteration_dir.name)
    return int(m.group(1)) if m else None


def load_feedback(iteration_dir: Path) -> dict:
    """Load feedback.json, returning a fresh skeleton if missing.

    Raises json.JSONDecodeError if the file exists but is corrupt — caller
    should catch and emit an error envelope.
    """
    path = _feedback_path(iteration_dir)
    if not path.is_file():
        return {
            "iteration": _parse_iteration(iteration_dir),
            "reviews": [],
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    # Normalize: ensure required keys exist
    data.setdefault("iteration", _parse_iteration(iteration_dir))
    data.setdefault("reviews", [])
    return data


def save_feedback(iteration_dir: Path, data: dict) -> None:
    path = _feedback_path(iteration_dir)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def cmd_add(args) -> int:
    iteration_dir = args.iteration_dir.resolve()
    if not iteration_dir.is_dir():
        return _fail(
            "not_found", "dir_missing",
            f"iteration directory not found: {iteration_dir}",
            param="--iteration-dir",
            hint="pass the path to iteration-N/ (created by init-workspace.py)",
        )

    try:
        data = load_feedback(iteration_dir)
    except json.JSONDecodeError as e:
        return _fail(
            "validation_error", "invalid_json",
            f"existing feedback.json is corrupt: {e}",
            param="--iteration-dir",
            hint=f"fix or delete {_feedback_path(iteration_dir)} and re-run",
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Update existing or append
    updated = False
    for review in data["reviews"]:
        if review.get("run_id") == args.run_id:
            review["feedback"] = args.feedback
            review["timestamp"] = now
            updated = True
            break
    if not updated:
        data["reviews"].append({
            "run_id": args.run_id,
            "feedback": args.feedback,
            "timestamp": now,
        })

    save_feedback(iteration_dir, data)

    result = {
        "ok": True,
        "action": "updated" if updated else "added",
        "run_id": args.run_id,
        "iteration_dir": str(iteration_dir),
        "feedback_path": str(_feedback_path(iteration_dir)),
        "total_reviews": len(data["reviews"]),
    }
    fmt = args.format or ("json" if not sys.stdout.isatty() else "pretty")
    if fmt == "pretty":
        print(f"  {result['action']} review for {args.run_id}", file=sys.stderr)
        print(f"  {result['total_reviews']} total review(s) in {result['feedback_path']}", file=sys.stderr)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_show(args) -> int:
    iteration_dir = args.iteration_dir.resolve()
    if not iteration_dir.is_dir():
        return _fail(
            "not_found", "dir_missing",
            f"iteration directory not found: {iteration_dir}",
            param="--iteration-dir",
            hint="pass the path to iteration-N/",
        )

    try:
        data = load_feedback(iteration_dir)
    except json.JSONDecodeError as e:
        return _fail(
            "validation_error", "invalid_json",
            f"feedback.json is corrupt: {e}",
            param="--iteration-dir",
            hint=f"fix or delete {_feedback_path(iteration_dir)}",
        )

    fmt = args.format or ("json" if not sys.stdout.isatty() else "pretty")
    if fmt == "pretty":
        reviews = data["reviews"]
        print(f"  iteration: {data.get('iteration')}", file=sys.stderr)
        print(f"  {len(reviews)} review(s)", file=sys.stderr)
        if not reviews:
            print(f"  (no feedback recorded yet)", file=sys.stderr)
        for r in reviews:
            fb = r.get("feedback", "")
            marker = "✗" if fb else "✓"
            preview = (fb[:80] + "...") if len(fb) > 80 else fb
            label = "comment" if fb else "fine"
            print(f"  {marker} {r['run_id']} ({label}): {preview}", file=sys.stderr)
        return 0

    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read/write feedback.json for benchmark eval iterations",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Add or update a single review")
    p_add.add_argument("--iteration-dir", type=Path, required=True,
                       help="Path to iteration-N/ directory")
    p_add.add_argument("--run-id", required=True,
                       help="Run identifier (e.g. eval-1/with_skill/run-1)")
    p_add.add_argument("--feedback", default="",
                       help="Review text (empty string = 'looked fine')")
    p_add.add_argument("--format", choices=["json", "pretty"], default=None,
                       help="Output format (default: json in pipe, pretty on TTY)")
    p_add.set_defaults(func=cmd_add)

    p_show = sub.add_parser("show", help="Print all reviews for an iteration")
    p_show.add_argument("--iteration-dir", type=Path, required=True,
                        help="Path to iteration-N/ directory")
    p_show.add_argument("--format", choices=["json", "pretty"], default=None,
                        help="Output format (default: json in pipe, pretty on TTY)")
    p_show.set_defaults(func=cmd_show)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
