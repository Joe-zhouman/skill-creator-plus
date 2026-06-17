# skill-creator-plus

> ⚠️ **This skill is under active iteration. Not stable.** Workflows, file paths, script names, and command-line flags may change between commits without notice. If you rely on it, pin to a commit, not a branch. See [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) for the current punch list of known friction points.

> 📖 **中文说明**：[README.zh.md](README.zh.md)

A meta-skill for [Claude Code](https://docs.claude.com/en/docs/claude-code) that creates, improves, and evaluates Claude Code skills. Itself a skill, used to bootstrap, lint, test, and iterate on other skills.

## What it does

Three workflows:

- **Create** — interview the user, draft a SKILL.md, run test cases, iterate
- **Improve** — take an existing skill, run the test-and-improve loop against the current version
- **Description Optimization** — tune the `description` field in frontmatter for better triggering accuracy (separate eval set, blind comparison)

The Test loop spawns subagents for `with_skill` vs `without_skill` runs (default 3 each), aggregates pass-rate / time / token cost into a benchmark, then walks the user through outputs to collect feedback.

## Five standards (Joe's)

Every skill produced by skill-creator-plus is held to:

1. **Subtraction filter** — only write what the model can't infer
2. **Layered structure** — progressive disclosure via `SKILL.md` + `references/`
3. **Determinism in code** — scripts for tasks with one right answer
4. **Tests mandatory** — workspace must show at least one Test loop run
5. **Agent-friendly CLI** — scripts with `--format`, structured errors, machine-readable output

Enforced by `scripts/check-skill.py`. Run it before every commit:

```bash
python3 scripts/check-skill.py .
```

Full text: [`references/joe-standard.md`](references/joe-standard.md).

## Install

```bash
git clone <repo-url> ~/.claude/skills/skill-creator-plus
```

Claude Code auto-discovers skills under `~/.claude/skills/`. The skill triggers when the user wants to create, modify, evaluate, or improve a skill.

For development (edit + immediately see changes globally), symlink instead:

```bash
git clone <repo-url> ~/src/skill-creator-plus
ln -s ~/src/skill-creator-plus ~/.claude/skills/skill-creator-plus
```

## Usage

Once installed, just describe what you want to the agent:

- "create a skill that converts PDF tables to CSV"
- "improve my existing PDF skill"
- "evaluate the quality of this skill someone sent me"

The skill itself documents its full workflow in [`SKILL.md`](SKILL.md).

## Layout

```
skill-creator-plus/
├── SKILL.md              # main workflow
├── KNOWN_ISSUES.md       # live punch list
├── scripts/              # scaffold, check-skill, init-workspace, aggregate, ...
├── references/           # Joe's standards, schemas, bad-example deconstructions
├── assets/agents/        # grader / comparator / analyzer prompts
└── tests/                # discipline tests, output checks, pytest for check-skill
```

## Contributing

This skill is its own dogfood — when you hit friction while using it, **don't silently work around it**. Append a note to [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) describing what you did, what you expected, what actually happened, and a one-line fix idea. The next iteration uses that file as its punch list.

## License

Apache 2.0. See [`LICENSE.txt`](LICENSE.txt) and [`NOTICE`](NOTICE).

Copyright 2026 Zhou, Man (Joe).
