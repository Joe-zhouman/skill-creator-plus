#!/usr/bin/env python3
"""validate-evals.py — Validate tests/evals/evals.json against schema.

Usage:
  validate-evals.py <evals-path>              # auto: pretty (TTY) or json (pipe)
  validate-evals.py <evals-path> --format json
  validate-evals.py <evals-path> --format pretty

Validates the structure of evals.json. Run after editing evals, before
spawning test runs. This is separate from check-skill.py (structural lint)
because schema validation is a different responsibility.

Exit codes:
  0 — all checks pass
  1 — validation errors found
  2 — file-level error (missing, not JSON, wrong args)
"""

import argparse
import json
import sys
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


def validate_evals(data: dict, path: Path) -> Dict[str, List[str]]:
    """Validate evals.json structure. Returns {errors: [], warnings: []}."""
    errors: List[str] = []
    warnings: List[str] = []

    # Top-level fields
    if "skill_name" not in data:
        errors.append("missing required field: skill_name")
    elif not isinstance(data["skill_name"], str) or not data["skill_name"].strip():
        errors.append("skill_name must be a non-empty string")

    if "evals" not in data:
        errors.append("missing required field: evals")
        return {"errors": errors, "warnings": warnings}

    if not isinstance(data["evals"], list):
        errors.append("evals must be an array")
        return {"errors": errors, "warnings": warnings}

    if len(data["evals"]) == 0:
        errors.append("evals array is empty — add at least one test case")
        return {"errors": errors, "warnings": warnings}

    # Per-eval checks
    seen_ids = set()
    for i, ev in enumerate(data["evals"]):
        prefix = f"evals[{i}]"

        if not isinstance(ev, dict):
            errors.append(f"{prefix}: must be an object, got {type(ev).__name__}")
            continue

        # id
        if "id" not in ev:
            errors.append(f"{prefix}: missing required field: id")
        elif not isinstance(ev["id"], int):
            errors.append(f"{prefix}: id must be an integer, got {type(ev['id']).__name__}")
        elif ev["id"] in seen_ids:
            errors.append(f"{prefix}: duplicate id {ev['id']}")
        else:
            seen_ids.add(ev["id"])

        # prompt
        if "prompt" not in ev:
            errors.append(f"{prefix}: missing required field: prompt")
        elif not isinstance(ev["prompt"], str) or not ev["prompt"].strip():
            errors.append(f"{prefix}: prompt must be a non-empty string")
        elif ev["prompt"].startswith("TODO"):
            warnings.append(f"{prefix}: prompt is still a TODO placeholder")

        # expected_output
        if "expected_output" not in ev:
            errors.append(f"{prefix}: missing required field: expected_output")
        elif not isinstance(ev["expected_output"], str) or not ev["expected_output"].strip():
            errors.append(f"{prefix}: expected_output must be a non-empty string")
        elif ev["expected_output"].startswith("TODO"):
            warnings.append(f"{prefix}: expected_output is still a TODO placeholder")

        # files (optional)
        if "files" in ev:
            if not isinstance(ev["files"], list):
                errors.append(f"{prefix}: files must be an array")
            else:
                for j, f in enumerate(ev["files"]):
                    if not isinstance(f, str):
                        errors.append(f"{prefix}.files[{j}]: must be a string")

        # expectations (optional)
        if "expectations" in ev:
            if not isinstance(ev["expectations"], list):
                errors.append(f"{prefix}: expectations must be an array")
            else:
                for j, exp in enumerate(ev["expectations"]):
                    if not isinstance(exp, str):
                        errors.append(f"{prefix}.expectations[{j}]: must be a string")

    return {"errors": errors, "warnings": warnings}


def format_json(result: dict) -> str:
    return json.dumps(result, indent=2, ensure_ascii=False)


def format_pretty(result: dict) -> str:
    lines = []
    for w in result["warnings"]:
        lines.append(f"  ⚠ {w}")
    for e in result["errors"]:
        lines.append(f"  ✗ {e}")
    if not result["errors"] and not result["warnings"]:
        lines.append(f"  ✓ {result['eval_count']} eval(s) OK")
    elif not result["errors"]:
        lines.append(f"\n  OK ({len(result['warnings'])} warning(s))")
    else:
        lines.append(f"\n  FAILED ({len(result['errors'])} error(s))")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate tests/evals/evals.json schema")
    parser.add_argument("evals_path", type=Path)
    parser.add_argument("--format", choices=["json", "pretty"], default=None,
                        help="Output format (default: json in pipe, pretty on TTY)")
    args = parser.parse_args()

    evals_path = args.evals_path.resolve()
    fmt = args.format or ("json" if not sys.stdout.isatty() else "pretty")

    if not evals_path.is_file():
        err = _error_envelope(
            "not_found", "file_missing",
            f"evals file not found: {evals_path}",
            hint="run gen-eval.py first, or check the path",
        )
        print(json.dumps(err), file=sys.stderr)
        return 2

    try:
        data = json.loads(evals_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        err = _error_envelope(
            "validation_error", "invalid_json",
            f"evals file is not valid JSON: {e}",
            hint="check for trailing commas, unquoted keys, or encoding issues",
        )
        print(json.dumps(err), file=sys.stderr)
        return 2

    if not isinstance(data, dict):
        err = _error_envelope(
            "validation_error", "invalid_structure",
            "evals file must contain a JSON object at the top level",
            hint=f"got {type(data).__name__} — wrap content in {{}}",
        )
        print(json.dumps(err), file=sys.stderr)
        return 2

    result = validate_evals(data, evals_path)
    result["eval_count"] = len(data.get("evals", []))
    result["ok"] = len(result["errors"]) == 0

    if fmt == "json":
        print(format_json(result))
    else:
        print(format_pretty(result))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
