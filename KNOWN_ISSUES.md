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

## 2026-06-17 scripts/ paths assume wrong cwd when creating another skill
- **What I did:** Used skill-creator-plus to scaffold `skill-eval`. Followed Step 0 instructions which say `python3 scripts/validate-evals.py tests/workspace/evals.json`.
- **Expected:** Validate the evals.json file I just generated.
- **Actual:** `python3: can't open file '/home/joe/skills/.repo/nature-skills/skills/skill-eval/scripts/validate-evals.py': [Errno 2] No such file or directory`. The agent's cwd was the target skill's directory (skill-eval), so the relative path resolved against skill-eval/scripts/, which doesn't contain validate-evals.py (that script belongs to skill-creator-plus).
- **Affected scripts (all of them, same root cause):** `gen-eval.py`, `init-workspace.py`, `validate-evals.py`, `aggregate_benchmark.py`, `feedback.py`, `check-skill.py`, `validate-grading.py`.
- **Fix idea:** Two options.
  (A) Add a "scripts location" preamble to the top of the test-loop section: "Before running any `scripts/...` command, locate this skill's own directory (the directory containing the SKILL.md you're currently reading). Use absolute paths from there." This is fragile — depends on the agent finding its own skill root.
  (B) Better: have the SKILL.md explicitly say "these scripts live in skill-creator-plus's own scripts/, not the target skill's scripts/ — invoke them by absolute path, e.g. `python3 ~/.claude/skills/skill-creator-plus/scripts/validate-evals.py <args>`". Hardcoded path assumes a standard install location, but that's the most common case. Make the path configurable via an env var for non-standard installs.
  Either way, every `scripts/...` reference in SKILL.md needs to be re-checked.
