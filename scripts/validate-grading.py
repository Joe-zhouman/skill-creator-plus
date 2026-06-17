#!/usr/bin/env python3
"""validate-grading.py — Validate grading.json against schema.

Usage:
  validate-grading.py <grading-path>              # auto: pretty (TTY) or json (pipe)
  validate-grading.py <grading-path> --format json
  validate-grading.py <grading-path> --format pretty

Validates the structure of grading.json. Run after grading, before
launching the viewer. The viewer depends on exact field names in the
expectations array — this script catches mismatches early.

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

REQUIRED_EXPECTATION_FIELDS = {"text", "passed", "evidence"}
FORBIDDEN_FIELDS = {"name", "met", "details"}


def _error_envelope(type_: str, subtype: str, message: str,
                    param: Optional[str] = None, hint: Optional[str] = None) -> dict:
    env = {"type": type_, "subtype": subtype, "message": message}
    if param is not None:
        env["param"] = param
    if hint is not None:
        env["hint"] = hint
    return env


def validate_grading(data: dict, path: Path) -> Dict[str, List[str]]:
    """Validate grading.json structure. Returns {errors: [], warnings: []}."""
    errors: List[str] = []
    warnings: List[str] = []

    if "expectations" not in data:
        errors.append("missing required field: expectations")
        return {"errors": errors, "warnings": warnings}

    if not isinstance(data["expectations"], list):
        errors.append("expectations must be an array")
        return {"errors": errors, "warnings": warnings}

    if len(data["expectations"]) == 0:
        warnings.append("expectations array is empty — nothing was graded")

    for i, exp in enumerate(data["expectations"]):
        prefix = f"expectations[{i}]"

        if not isinstance(exp, dict):
            errors.append(f"{prefix}: must be an object, got {type(exp).__name__}")
            continue

        # Check for forbidden fields (common wrong names)
        found_forbidden = FORBIDDEN_FIELDS & set(exp.keys())
        if found_forbidden:
            errors.append(
                f"{prefix}: uses forbidden field(s) {sorted(found_forbidden)} — "
                f"the viewer requires {sorted(REQUIRED_EXPECTATION_FIELDS)}"
            )

        # Check required fields
        missing = REQUIRED_EXPECTATION_FIELDS - set(exp.keys())
        if missing:
            errors.append(f"{prefix}: missing required field(s): {sorted(missing)}")

        # Type checks for present fields
        if "text" in exp and not isinstance(exp["text"], str):
            errors.append(f"{prefix}.text: must be a string")
        if "passed" in exp and not isinstance(exp["passed"], bool):
            errors.append(f"{prefix}.passed: must be a boolean")
        if "evidence" in exp and not isinstance(exp["evidence"], str):
            errors.append(f"{prefix}.evidence: must be a string")

    # summary is optional but if present, check structure
    if "summary" in data:
        s = data["summary"]
        if not isinstance(s, dict):
            errors.append("summary must be an object")
        else:
            for field in ("passed", "failed", "total"):
                if field in s and not isinstance(s[field], int):
                    errors.append(f"summary.{field}: must be an integer")
            if "pass_rate" in s and not isinstance(s["pass_rate"], (int, float)):
                errors.append("summary.pass_rate: must be a number")

    return {"errors": errors, "warnings": warnings}


def format_pretty(result: dict) -> str:
    lines = []
    for w in result["warnings"]:
        lines.append(f"  ⚠ {w}")
    for e in result["errors"]:
        lines.append(f"  ✗ {e}")
    if not result["errors"] and not result["warnings"]:
        lines.append(f"  ✓ {result['expectation_count']} expectation(s) OK")
    elif not result["errors"]:
        lines.append(f"\n  OK ({len(result['warnings'])} warning(s))")
    else:
        lines.append(f"\n  FAILED ({len(result['errors'])} error(s))")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate grading.json schema")
    parser.add_argument("grading_path", type=Path)
    parser.add_argument("--format", choices=["json", "pretty"], default=None,
                        help="Output format (default: json in pipe, pretty on TTY)")
    args = parser.parse_args()

    grading_path = args.grading_path.resolve()
    fmt = args.format or ("json" if not sys.stdout.isatty() else "pretty")

    if not grading_path.is_file():
        err = _error_envelope(
            "not_found", "file_missing",
            f"grading file not found: {grading_path}",
            hint="run the grader first, or check the path",
        )
        print(json.dumps(err), file=sys.stderr)
        return 2

    try:
        data = json.loads(grading_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        err = _error_envelope(
            "validation_error", "invalid_json",
            f"grading file is not valid JSON: {e}",
            hint="check for trailing commas, unquoted keys, or encoding issues",
        )
        print(json.dumps(err), file=sys.stderr)
        return 2

    if not isinstance(data, dict):
        err = _error_envelope(
            "validation_error", "invalid_structure",
            "grading file must contain a JSON object at the top level",
            hint=f"got {type(data).__name__} — wrap content in {{}}",
        )
        print(json.dumps(err), file=sys.stderr)
        return 2

    result = validate_grading(data, grading_path)
    result["expectation_count"] = len(data.get("expectations", []))
    result["ok"] = len(result["errors"]) == 0

    if fmt == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_pretty(result))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
