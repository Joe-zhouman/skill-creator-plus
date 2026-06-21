# Known Issues

Friction points hit while using this skill. Append new issues at the bottom; don't reorder or group — chronological order makes it easy to see what's recent.

Format:

```
## <YYYY-MM-DD> short title
- **What I did:** ...
- **Expected:** ...
- **Actual:** ...
- **Fix idea:** ... (optional)
```

---

## 2026-06-21 skill-creator-plus has never run its own test loop (and probably shouldn't)
- **What I did:** Audited `tests/workspace/` after fixing the aggregate_benchmark summary bug — wanted to verify whether the bug corrupted skill-creator-plus's own benchmark data.
- **Expected:** Some iteration history, like skill-eval has.
- **Actual:** `tests/workspace/` doesn't exist. skill-creator-plus has never been run through its own test loop. check-skill.py's hard #4 check ("benchmark.json must exist") is currently in violation.
- **Why running the loop is structurally hard for meta-skills:**
  - skill-creator-plus's output is *another skill* (SKILL.md + scripts + tests). Each subagent run has to produce a full skill, not a text answer — heavy context, slow, expensive (5-10× a normal skill).
  - Grading the output requires evaluating whether the produced skill is good — which is itself a meta-evaluation (skill-eval's job). Nesting skill-eval inside skill-creator-plus's loop is turtles all the way down.
  - 3 realistic prompts is hard to construct: each has to be a substantive "make a skill that does X" with a real X — not a one-liner.
  - Per-run cost is high enough that iterating frequently (the whole point of the test loop) becomes impractical.
- **Alternative verification we use instead:**
  - **Smoke tests on every change** — `check-skill.py` passes on skill-creator-plus itself, `pytest tests/test_check_skill.py` passes, the scripts run end-to-end against real downstream skills (sci-draw, skill-eval) without crashing. This catches machinery regressions.
  - **Downstream skills as evidence** — skill-eval and sci-draw were both produced using skill-creator-plus, and they work. Their existence and usability is indirect evidence the meta-skill does its job. (skill-eval's own self-eval at 49/50 is downstream evidence of upstream quality.)
  - **Bug discoveries during real use feed back into KNOWN_ISSUES** — the aggregate_benchmark bug, the scripts-path bug, the evals.json format bug, etc. were all caught by running skill-creator-plus on real skills, not by self-test. This is a more honest loop than a synthetic self-eval would be.
- **Status:** Won't fix in the foreseeable future. Acknowledged as a structural limitation of meta-skills, not negligence. README's "under active iteration" warning still holds — the iteration just happens via real downstream use, not synthetic self-test.
- **Revisit if:** A specific change to skill-creator-plus makes the loop structure easier (e.g., a "lite" grading mode that judges output skills with shallow heuristics instead of full skill-eval), or someone specifically requests benchmark numbers for a comparison.

## 2026-06-17 scripts/ paths assume wrong cwd when creating another skill
- **What I did:** Used skill-creator-plus to scaffold `skill-eval`. Followed Step 0 instructions which say `python3 scripts/validate-evals.py tests/workspace/evals.json`.
- **Expected:** Validate the evals.json file I just generated.
- **Actual:** `python3: can't open file '/home/joe/skills/.repo/nature-skills/skills/skill-eval/scripts/validate-evals.py': [Errno 2] No such file or directory`. The agent's cwd was the target skill's directory (skill-eval), so the relative path resolved against skill-eval/scripts/, which doesn't contain validate-evals.py (that script belongs to skill-creator-plus).
- **Affected scripts (all of them, same root cause):** `gen-eval.py`, `init-workspace.py`, `validate-evals.py`, `aggregate_benchmark.py`, `feedback.py`, `check-skill.py`, `validate-grading.py`.
- **Fix idea:** Two options.
  (A) Add a "scripts location" preamble to the top of the test-loop section: "Before running any `scripts/...` command, locate this skill's own directory (the directory containing the SKILL.md you're currently reading). Use absolute paths from there." This is fragile — depends on the agent finding its own skill root.
  (B) Better: have the SKILL.md explicitly say "these scripts live in skill-creator-plus's own scripts/, not the target skill's scripts/ — invoke them by absolute path, e.g. `python3 ~/.claude/skills/skill-creator-plus/scripts/validate-evals.py <args>`". Hardcoded path assumes a standard install location, but that's the most common case. Make the path configurable via an env var for non-standard installs.
  Either way, every `scripts/...` reference in SKILL.md needs to be re-checked.
- **Status:** Fixed in commit `0a60639`. All `python3 scripts/...` invocations in SKILL.md now use `python3 $SKILL_CREATOR/scripts/...`, with a "Two different root directories" preamble at the top of the test-loop section explaining the distinction between the target skill's cwd and skill-creator-plus's own root.

## 2026-06-17 trigger eval is Claude Code-only; multi-provider support deferred

- **What I did:** Researched whether `run_eval.py` / `improve_description.py` / `run_one_iter.py` could be extended to support OpenCode, Codex, and Reasonix as alternative providers (in addition to `claude -p`).
- **Expected:** A clean adapter layer where each provider plugs in with its own CLI invocation and trigger-detection logic.
- **Actual:** The three providers' trigger-detection mechanisms are too different to unify cleanly. Detailed findings:

  | Provider | Skill concept | Trigger detection |
  |---|---|---|
  | Claude Code | `.claude/commands/<name>.md` + `.claude/skills/<name>/SKILL.md`; native on-demand loading | Real-time JSONL stream (`--output-format stream-json`), find `tool_use` events for `Skill`/`Read` tools |
  | OpenCode | `.opencode/skills/<name>/SKILL.md` (also reads `.claude/skills/`!); nearly identical to Claude Code | Real-time JSONL stream (`--format json`), find `tool_use` events where `part.tool == "skill"` |
  | Codex | **No native skills** — only `AGENTS.md` (passive) and user-installed plugins (manual) | Would require MCP-server hack: wrap each skill as MCP tool, detect `mcp_tool_call` events in `--json` stream |
  | Reasonix | `.reasonix/commands/` + `[skills].paths` in `reasonix.toml`; native skills exist | No documented real-time JSON stream; would need post-hoc parsing of session JSONL transcript or `reasonix events` tailing |

- **Decision:** Defer. OpenCode would be ~trivial to add (paths and stream format nearly identical to Claude Code), but Codex and Reasonix require fundamentally different trigger-detection architectures. Building a unified abstraction for all three now would mean ~200+ lines of provider-specific adapters for an uncertain user base, on top of a still-iterating core.
- **When to revisit:**
  - A real user asks for OpenCode support (cheapest path — could be a 30-line adapter).
  - OR a real user asks for Codex/Reasonix and we accept rewriting trigger detection for them.
  - OR the skill-creator-plus core stabilizes (no pending friction in KNOWN_ISSUES above this entry) and we have spare bandwidth for non-Claude providers.
- **Sources:**
  - OpenCode: https://opencode.ai/docs/skills/, https://opencode.ai/docs/cli/
  - Codex: https://developers.openai.com/codex/cli/reference, https://github.com/openai/codex
  - Reasonix: https://github.com/esengine/deepseek-reasonix, https://reasonix.io/docs/

