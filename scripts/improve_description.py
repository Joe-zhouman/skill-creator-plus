#!/usr/bin/env python3
"""Improve a skill description based on eval results.

Takes eval results (from run_one_iter.py) and generates an improved description
by calling `claude -p` as a subprocess (same auth pattern as run_one_iter.py —
uses the session's Claude Code auth, no separate ANTHROPIC_API_KEY needed).

This is a library AND a CLI:
- Library: `from scripts.improve_description import improve_description` — call
  directly when orchestrating in-process (e.g., from another script).
- CLI: `python3 -m scripts.improve_description --eval-results <path> ...` — call
  from the AGENT when you want a candidate description without writing one yourself.

CLI usage is OPTIONAL in the description-optimization flow. The AGENT can also
just write a new description directly based on user feedback. This script exists
for the case where the AGENT wants a second-opinion draft.

Usage:
  improve_description.py --eval-results <path> --skill-path <path> --model <model>
                         [--history <path>] [--format json|pretty]

Reads eval results JSON (the iter-N.json from run_one_iter.py), calls claude -p
with a tuned prompt (don't overfit, 100-200 words, imperative voice), and prints
the new description + updated history as JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

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


def _call_claude(prompt: str, model: str | None, timeout: int = 300) -> str:
    """Run `claude -p` with the prompt on stdin and return the text response.

    Prompt goes over stdin (not argv) because it embeds the full SKILL.md
    body and can easily exceed comfortable argv length.
    """
    cmd = ["claude", "-p", "--output-format", "text"]
    if model:
        cmd.extend(["--model", model])

    # Remove CLAUDECODE env var to allow nesting claude -p inside a
    # Claude Code session. The guard is for interactive terminal conflicts;
    # programmatic subprocess usage is safe. Same pattern as run_eval.py.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude -p exited {result.returncode}\nstderr: {result.stderr}"
        )
    return result.stdout


def improve_description(
    skill_name: str,
    skill_content: str,
    current_description: str,
    eval_results: dict,
    history: list[dict],
    model: str,
    test_results: dict | None = None,
    log_dir: Path | None = None,
    iteration: int | None = None,
) -> str:
    """Call Claude to improve the description based on eval results."""
    failed_triggers = [
        r for r in eval_results["results"]
        if r["should_trigger"] and not r["pass"]
    ]
    false_triggers = [
        r for r in eval_results["results"]
        if not r["should_trigger"] and not r["pass"]
    ]

    # Build scores summary
    train_score = f"{eval_results['summary']['passed']}/{eval_results['summary']['total']}"
    if test_results:
        test_score = f"{test_results['summary']['passed']}/{test_results['summary']['total']}"
        scores_summary = f"Train: {train_score}, Test: {test_score}"
    else:
        scores_summary = f"Train: {train_score}"

    prompt = f"""You are optimizing a skill description for a Claude Code skill called "{skill_name}". A "skill" is sort of like a prompt, but with progressive disclosure -- there's a title and description that Claude sees when deciding whether to use the skill, and then if it does use the skill, it reads the .md file which has lots more details and potentially links to other resources in the skill folder like helper files and scripts and additional documentation or examples.

The description appears in Claude's "available_skills" list. When a user sends a query, Claude decides whether to invoke the skill based solely on the title and on this description. Your goal is to write a description that triggers for relevant queries, and doesn't trigger for irrelevant ones.

Here's the current description:
<current_description>
"{current_description}"
</current_description>

Current scores ({scores_summary}):
<scores_summary>
"""
    if failed_triggers:
        prompt += "FAILED TO TRIGGER (should have triggered but didn't):\n"
        for r in failed_triggers:
            prompt += f'  - "{r["query"]}" (triggered {r["triggers"]}/{r["runs"]} times)\n'
        prompt += "\n"

    if false_triggers:
        prompt += "FALSE TRIGGERS (triggered but shouldn't have):\n"
        for r in false_triggers:
            prompt += f'  - "{r["query"]}" (triggered {r["triggers"]}/{r["runs"]} times)\n'
        prompt += "\n"

    if history:
        prompt += "PREVIOUS ATTEMPTS (do NOT repeat these — try something structurally different):\n\n"
        for h in history:
            train_s = f"{h.get('train_passed', h.get('passed', 0))}/{h.get('train_total', h.get('total', 0))}"
            test_s = f"{h.get('test_passed', '?')}/{h.get('test_total', '?')}" if h.get('test_passed') is not None else None
            score_str = f"train={train_s}" + (f", test={test_s}" if test_s else "")
            prompt += f'<attempt {score_str}>\n'
            prompt += f'Description: "{h["description"]}"\n'
            if "results" in h:
                prompt += "Train results:\n"
                for r in h["results"]:
                    status = "PASS" if r["pass"] else "FAIL"
                    prompt += f'  [{status}] "{r["query"][:80]}" (triggered {r["triggers"]}/{r["runs"]})\n'
            if h.get("note"):
                prompt += f'Note: {h["note"]}\n'
            prompt += "</attempt>\n\n"

    prompt += f"""</scores_summary>

Skill content (for context on what the skill does):
<skill_content>
{skill_content}
</skill_content>

Based on the failures, write a new and improved description that is more likely to trigger correctly. When I say "based on the failures", it's a bit of a tricky line to walk because we don't want to overfit to the specific cases you're seeing. So what I DON'T want you to do is produce an ever-expanding list of specific queries that this skill should or shouldn't trigger for. Instead, try to generalize from the failures to broader categories of user intent and situations where this skill would be useful or not useful. The reason for this is twofold:

1. Avoid overfitting
2. The list might get loooong and it's injected into ALL queries and there might be a lot of skills, so we don't want to blow too much space on any given description.

Concretely, your description should not be more than about 100-200 words, even if that comes at the cost of accuracy. There is a hard limit of 1024 characters — descriptions over that will be truncated, so stay comfortably under it.

Here are some tips that we've found to work well in writing these descriptions:
- The skill should be phrased in the imperative -- "Use this skill for" rather than "this skill does"
- The skill description should focus on the user's intent, what they are trying to achieve, vs. the implementation details of how the skill works.
- The description competes with other skills for Claude's attention — make it distinctive and immediately recognizable.
- If you're getting lots of failures after repeated attempts, change things up. Try different sentence structures or wordings.

I'd encourage you to be creative and mix up the style in different iterations since you'll have multiple opportunities to try different approaches and we'll just grab the highest-scoring one at the end. 

Please respond with only the new description text in <new_description> tags, nothing else."""

    text = _call_claude(prompt, model)

    match = re.search(r"<new_description>(.*?)</new_description>", text, re.DOTALL)
    description = match.group(1).strip().strip('"') if match else text.strip().strip('"')

    transcript: dict = {
        "iteration": iteration,
        "prompt": prompt,
        "response": text,
        "parsed_description": description,
        "char_count": len(description),
        "over_limit": len(description) > 1024,
    }

    # Safety net: the prompt already states the 1024-char hard limit, but if
    # the model blew past it anyway, make one fresh single-turn call that
    # quotes the too-long version and asks for a shorter rewrite. (The old
    # SDK path did this as a true multi-turn; `claude -p` is one-shot, so we
    # inline the prior output into the new prompt instead.)
    if len(description) > 1024:
        shorten_prompt = (
            f"{prompt}\n\n"
            f"---\n\n"
            f"A previous attempt produced this description, which at "
            f"{len(description)} characters is over the 1024-character hard limit:\n\n"
            f'"{description}"\n\n'
            f"Rewrite it to be under 1024 characters while keeping the most "
            f"important trigger words and intent coverage. Respond with only "
            f"the new description in <new_description> tags."
        )
        shorten_text = _call_claude(shorten_prompt, model)
        match = re.search(r"<new_description>(.*?)</new_description>", shorten_text, re.DOTALL)
        shortened = match.group(1).strip().strip('"') if match else shorten_text.strip().strip('"')

        transcript["rewrite_prompt"] = shorten_prompt
        transcript["rewrite_response"] = shorten_text
        transcript["rewrite_description"] = shortened
        transcript["rewrite_char_count"] = len(shortened)
        description = shortened

    transcript["final_description"] = description

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"improve_iter_{iteration or 'unknown'}.json"
        log_file.write_text(json.dumps(transcript, indent=2))

    return description


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Improve a skill description based on eval results (optional helper)",
    )
    parser.add_argument("--eval-results", type=Path, required=True,
                        help="Path to eval results JSON (iter-N.json from run_one_iter.py)")
    parser.add_argument("--skill-path", type=Path, required=True,
                        help="Path to skill directory")
    parser.add_argument("--history", type=Path, default=None,
                        help="Path to history JSON (previous attempts, prevents repetition)")
    parser.add_argument("--model", required=True,
                        help="Model for improvement (use the model powering the current session)")
    parser.add_argument("--format", choices=["json", "pretty"], default=None,
                        help="Output format (default: json in pipe, pretty on TTY)")
    args = parser.parse_args()

    fmt = args.format or ("json" if not sys.stdout.isatty() else "pretty")

    # Validate eval-results
    eval_results_path = args.eval_results.resolve()
    if not eval_results_path.is_file():
        return _fail(
            "not_found", "file_missing",
            f"eval-results file not found: {eval_results_path}",
            param="--eval-results",
            hint="pass the path to iter-N.json from run_one_iter.py",
        )
    try:
        eval_results = json.loads(eval_results_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return _fail(
            "validation_error", "invalid_json",
            f"eval-results file is not valid JSON: {e}",
            param="--eval-results",
            hint="check for trailing commas, unquoted keys, or encoding issues",
        )
    if not isinstance(eval_results, dict) or "results" not in eval_results:
        return _fail(
            "validation_error", "invalid_structure",
            "eval-results must be an object with a 'results' array",
            param="--eval-results",
            hint="expected the iter-N.json format from run_one_iter.py",
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
    if not (skill_path / "SKILL.md").is_file():
        return _fail(
            "not_found", "file_missing",
            f"no SKILL.md in skill directory: {skill_path}",
            param="--skill-path",
            hint="every skill must have a SKILL.md at its root",
        )

    try:
        name, _, content = parse_skill_md(skill_path)
    except ValueError as e:
        return _fail(
            "validation_error", "invalid_frontmatter",
            f"SKILL.md frontmatter is invalid: {e}",
            param="--skill-path",
            hint="SKILL.md must start with '---' and close with a matching '---'",
        )

    # History is optional
    history = []
    if args.history is not None:
        history_path = args.history.resolve()
        if not history_path.is_file():
            return _fail(
                "not_found", "file_missing",
                f"history file not found: {history_path}",
                param="--history",
                hint="omit --history for the first iteration, or pass a valid history JSON",
            )
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return _fail(
                "validation_error", "invalid_json",
                f"history file is not valid JSON: {e}",
                param="--history",
                hint="history should be an array of previous {description, passed, total, results} entries",
            )

    current_description = eval_results.get("description", "")
    if not current_description:
        return _fail(
            "validation_error", "missing_field",
            "eval-results has no 'description' field — cannot improve",
            param="--eval-results",
            hint="run_one_iter.py writes the tested description into iter-N.json; use that file",
        )

    if fmt == "pretty":
        print(f"  skill: {name}", file=sys.stderr)
        print(f"  current pass rate: {eval_results.get('summary', {}).get('passed', '?')}/{eval_results.get('summary', {}).get('total', '?')}", file=sys.stderr)
        print(f"  calling claude -p for a candidate description...", file=sys.stderr)

    try:
        new_description = improve_description(
            skill_name=name,
            skill_content=content,
            current_description=current_description,
            eval_results=eval_results,
            history=history,
            model=args.model,
        )
    except RuntimeError as e:
        return _fail(
            "runtime_error", "claude_call_failed",
            f"claude -p call failed: {e}",
            hint="check that the model ID is valid and claude CLI is authenticated",
            exit_code=1,
        )

    output = {
        "description": new_description,
        "over_limit": len(new_description) > 1024,
        "char_count": len(new_description),
        "history": history + [{
            "description": current_description,
            "passed": eval_results["summary"]["passed"],
            "failed": eval_results["summary"]["failed"],
            "total": eval_results["summary"]["total"],
            "results": eval_results["results"],
        }],
    }

    if fmt == "pretty":
        print(f"  candidate ({len(new_description)} chars):", file=sys.stderr)
        print(f"  {new_description}", file=sys.stderr)
        if output["over_limit"]:
            print(f"  WARNING: over 1024-char limit, needs trimming", file=sys.stderr)
        print(f"\n  Review this candidate with the user before applying.", file=sys.stderr)
    print(json.dumps(output, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
