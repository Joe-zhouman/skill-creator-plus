#!/usr/bin/env python3
"""check-skill.py — Static lint against Joe's #1–#5 standards.

Usage:
  check-skill.py <skill-path>              # auto: pretty (TTY) or json (pipe)
  check-skill.py <skill-path> --format json
  check-skill.py <skill-path> --format pretty
  check-skill.py <skill-path> --format table
  check-skill.py <skill-path> --verbose    # show what was checked

Hard checks (exit non-zero on failure):
  - SKILL.md exists and has YAML frontmatter (--- ... ---)
  - YAML frontmatter has both `name` and `description` fields
  - SKILL.md is at most 500 lines
  - Every relative path referenced from SKILL.md exists
  - Every file in scripts/ is executable
  - tests/ directory exists and is non-empty (#4)

Soft checks (warnings, never fail):
  - reference files >300 lines should include a table of contents
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# TOC convention: a "## Table of Contents" heading followed by a multi-level
# unordered list (plain text or anchor links both accepted). The heading is
# the signal — agents don't need anchor links, but a labeled section disambiguates
# the TOC from incidental lists elsewhere in the file.
TOC_HEADING_PATTERN = re.compile(r"^#{1,6}\s*Table of Contents\s*$", re.MULTILINE | re.IGNORECASE)
TOC_LIST_PATTERN = re.compile(r"^\s*[-*]\s+.+", re.MULTILINE)

# Files matching this pattern are exempt from the TOC check — they are
# intentionally tutorial-style references (e.g. bad-example deconstructions).
TOC_EXEMPT_PATTERN = re.compile(r"bad-example")

YAML_REQUIRED_FIELDS = {"name", "description"}


def _error_envelope(type_: str, subtype: str, message: str,
                    param: Optional[str] = None, hint: Optional[str] = None) -> dict:
    """Build a #5-compliant error envelope."""
    env = {"type": type_, "subtype": subtype, "message": message}
    if param is not None:
        env["param"] = param
    if hint is not None:
        env["hint"] = hint
    return env


def _has_toc(text: str) -> bool:
    """True if markdown text contains a labeled Table of Contents.

    Convention: a "## Table of Contents" heading followed by a multi-level
    unordered list. Plain text entries are accepted — anchor links are not
    required (agents read the text, they don't click links).
    """
    if not TOC_HEADING_PATTERN.search(text):
        return False
    heading_match = TOC_HEADING_PATTERN.search(text)
    after_heading = text[heading_match.end():]
    list_items = TOC_LIST_PATTERN.findall(after_heading)
    top_level = [item for item in list_items if not item.startswith((" ", "\t"))]
    return len(top_level) >= 2


def has_yaml_frontmatter(skill_md: Path) -> bool:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False
    closing = text.find("\n---", 3)
    if closing == -1:
        return False
    after = closing + 4
    return after >= len(text) or text[after] == "\n"


def parse_yaml_fields(skill_md: Path) -> set:
    """Extract top-level keys from YAML frontmatter (minimal parser)."""
    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines[0] != "---":
        return set()
    end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), -1)
    if end == -1:
        return set()
    keys = set()
    for line in lines[1:end]:
        m = re.match(r"^(\w[\w-]*)\s*:", line)
        if m:
            keys.add(m.group(1))
    return keys


def collect_markdown_links(text: str) -> list:
    links = []
    for m in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text):
        links.append(m.group(1))
    return links


def lint_skill(skill: Path) -> dict:
    """Run all checks, return result dict with errors, warnings, checks."""
    errors: list = []
    warnings: list = []
    checks_run: list = []

    skill_md = skill / "SKILL.md"
    if not skill_md.is_file():
        errors.append("SKILL.md missing")
        checks_run.append("SKILL.md exists")
    else:
        checks_run.append("SKILL.md exists")

        # YAML frontmatter
        if not has_yaml_frontmatter(skill_md):
            errors.append("SKILL.md missing YAML frontmatter (must start and close with `---`)")
        checks_run.append("YAML frontmatter")

        # YAML required fields
        fields = parse_yaml_fields(skill_md)
        for f in sorted(YAML_REQUIRED_FIELDS):
            if f not in fields:
                errors.append(f"YAML frontmatter missing required field: {f}")
        checks_run.append("YAML fields (name, description)")

        # Line count
        text = skill_md.read_text(encoding="utf-8")
        line_count = text.count("\n") + 1
        if line_count > 500:
            errors.append(f"SKILL.md is {line_count} lines (limit: 500 — move detail to references/)")
        checks_run.append(f"line count ({line_count}/500)")

        # Reference resolution
        for target in collect_markdown_links(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            # Markdown anchors (e.g. "references/foo.md#section") are valid
            # navigation but the filesystem only sees the path before '#'.
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue  # pure anchor like "#section", already filtered above
            resolved = (skill / path_part).resolve()
            if not resolved.exists():
                errors.append(f"SKILL.md references missing file: {target}")
        checks_run.append("reference resolution")

    # Soft check: large reference files should have a TOC
    # (bad-example files are exempt — they intentionally demonstrate anti-patterns)
    refs_dir = skill / "references"
    if refs_dir.is_dir():
        for ref in refs_dir.iterdir():
            if ref.is_file() and ref.suffix == ".md":
                if TOC_EXEMPT_PATTERN.search(ref.name):
                    continue
                ref_text = ref.read_text(encoding="utf-8")
                ref_lines = ref_text.count("\n") + 1
                if ref_lines > 300 and not _has_toc(ref_text):
                    warnings.append(
                        f"references/{ref.name} is {ref_lines} lines with no table of contents "
                        f"(add a '## Table of Contents' section with a list of sections)"
                    )
    checks_run.append("reference files TOC (soft)")

    # tests/ must exist with real content (workspace/ doesn't count) (#4)
    tests_dir = skill / "tests"
    if not tests_dir.is_dir():
        errors.append("tests/ directory missing (#4 violation)")
    else:
        non_workspace = [p for p in tests_dir.iterdir() if p.name != "workspace"]
        if not non_workspace:
            errors.append("tests/ directory has no test content (#4 violation — add evals.json or manual checks; workspace/ is run state, not test content)")
    checks_run.append("tests/ present and non-empty")

    # tests must have been run (#4): at least one benchmark.json proves the loop ran
    workspace_dir = tests_dir / "workspace" if tests_dir.is_dir() else None
    benchmarks = list(workspace_dir.glob("iteration-*/benchmark.json")) if workspace_dir and workspace_dir.is_dir() else []
    if not benchmarks:
        errors.append(
            "no benchmark.json found — Test loop hasn't been run (#4 violation). "
            "Run init-workspace, spawn runs, grade, then aggregate at least once before deployment."
        )
    checks_run.append("Test loop executed (benchmark.json present)")

    # scripts executable
    scripts_dir = skill / "scripts"
    if scripts_dir.is_dir():
        for s in scripts_dir.iterdir():
            if s.is_file() and not s.name.startswith(".") and s.name.endswith((".sh", ".py")):
                if not os.access(s, os.X_OK):
                    errors.append(f"script not executable: {s.name}")
        checks_run.append("scripts executable")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "checks_run": checks_run,
    }


def format_json(result: dict) -> str:
    return json.dumps(result, indent=2, ensure_ascii=False)


def format_pretty(result: dict) -> str:
    lines = []
    for c in result["checks_run"]:
        lines.append(f"  ✓ {c}")
    for w in result["warnings"]:
        lines.append(f"  ⚠ {w}")
    for e in result["errors"]:
        lines.append(f"  ✗ {e}")
    lines.append("")
    if result["ok"]:
        lines.append("OK")
    else:
        lines.append(f"FAILED ({len(result['errors'])} error(s))")
    return "\n".join(lines)


def format_table(result: dict) -> str:
    lines = ["Status  Check", "------  -----"]
    for c in result["checks_run"]:
        lines.append(f"    ok   {c}")
    for w in result["warnings"]:
        lines.append(f"  warn   {w}")
    for e in result["errors"]:
        lines.append(f"  FAIL   {e}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Static lint for skill structure")
    parser.add_argument("skill_path", type=Path)
    parser.add_argument("--format", choices=["json", "pretty", "table"],
                        default=None, help="Output format (default: json in pipe, pretty on TTY)")
    parser.add_argument("--verbose", action="store_true", help="Log checks to stderr")
    args = parser.parse_args()

    # Resolve skill path
    skill = args.skill_path.resolve()
    if not skill.is_dir():
        err = _error_envelope(
            "validation_error", "invalid_argument",
            "skill-path must be a directory",
            param="--skill-path",
            hint=f"pass the absolute path to a skill directory, e.g. /home/me/skills/my-skill",
        )
        print(json.dumps(err), file=sys.stderr)
        return 2

    # Run lint
    result = lint_skill(skill)

    # Determine format
    fmt = args.format
    if fmt is None:
        fmt = "json" if not sys.stdout.isatty() else "pretty"

    # Output data → stdout (#5.4)
    if fmt == "json":
        print(format_json(result))
    elif fmt == "table":
        print(format_table(result))
    else:
        print(format_pretty(result))

    # Verbose log → stderr
    if args.verbose:
        print(f"checks run: {', '.join(result['checks_run'])}", file=sys.stderr)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
