#!/usr/bin/env python3
"""gen-eval.py — Generate a starter evals.json for a new skill.

Usage: gen-eval.py <skill-name> <output-path>

Joe custom addition on top of the official skill-creator. The starter
contains 3 should-trigger prompts with empty expectation lists — these
are output-quality test cases (the prompt genuinely needs the skill and
runs through the with-skill vs without-skill loop). should-not-trigger
queries belong to Description Optimization and live in a separate file;
they are intentionally NOT mixed into this starter.

Recommended output path: tests/evals/evals.json (inside the skill directory).
"""

import json
import sys
from pathlib import Path

STARTER_EVALS = [
    {
        "id": 1,
        "prompt": "TODO: replace with a realistic should-trigger prompt.",
        "expected_output": "TODO",
        "expectations": [],
    },
    {
        "id": 2,
        "prompt": "TODO: replace with a second should-trigger prompt (different phrasing).",
        "expected_output": "TODO",
        "expectations": [],
    },
    {
        "id": 3,
        "prompt": "TODO: replace with a third should-trigger prompt (edge case).",
        "expected_output": "TODO",
        "expectations": [],
    },
]


def _error_envelope(type_: str, subtype: str, message: str,
                    param=None, hint=None):
    env = {"type": type_, "subtype": subtype, "message": message}
    if param is not None:
        env["param"] = param
    if hint is not None:
        env["hint"] = hint
    return env


def main() -> int:
    if len(sys.argv) != 3:
        err = _error_envelope(
            "usage_error", "missing_arguments",
            "expected exactly 2 arguments: <skill-name> <output-path>",
            hint="e.g. gen-eval.py my-skill tests/workspace/evals.json",
        )
        print(json.dumps(err), file=sys.stderr)
        return 2

    skill_name = sys.argv[1]
    output_path = Path(sys.argv[2])

    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "skill_name": skill_name,
        "evals": STARTER_EVALS,
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    result = {"ok": True, "wrote": str(output_path), "eval_count": len(STARTER_EVALS)}
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
