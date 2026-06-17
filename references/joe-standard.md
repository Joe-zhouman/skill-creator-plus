# Joe's Standards — Custom layer on top of the official skill-creator

These standards are the customization Joe adds to the official Claude skill-creator workflow. They apply to every skill created through `skill-creator++`.

## #1 Subtraction filter

Before adding any sentence, ask: **"Does the model already know this?"**

- Known → don't write it.
- Unknown → write it freely (examples, why-explanations, how-to steps all permitted when genuinely needed).
- **Uncertain → default to "it doesn't know" and write it.** It's easy to overestimate what the model knows. Removing a load-bearing sentence in a later review pass is cheap; shipping a skill that silently omits a key constraint is expensive.

This is a content filter, not a style rule. The default is to ship only what is load-bearing.

**Scope of "known":** common languages, popular frameworks (numpy, requests, React), and standard library APIs qualify as known. Niche libraries, internal tooling, project-specific conventions, and domain-specific jargon do not — assume the model needs those spelled out.

**Why:** Every line in SKILL.md costs context tokens on every invocation. The model already knows matplotlib's API, Python syntax, common CLI patterns. Writing what it already knows is waste — it doesn't improve output quality, it just burns tokens and dilutes the signal. The skill's value is in encoding judgment the model lacks, not knowledge it already has.

**For what remains:** explain the *why*, not just the *what*. "Use constrained_layout=True" tells the model nothing it can't find in the API docs. "Use constrained_layout=True — without it, overlapping labels are common in multi-panel figures, and the alternative (tight_layout) breaks with suptitles" gives the model a reason it can use to judge edge cases. A good why makes rigid MUSTs unnecessary — the model generalizes from the reason rather than following a brittle rule.

## #2 Layered structure + progressive disclosure

Four directories on disk, three loading levels at runtime. Content must be routed to the right layer — both where it lives and when it loads.

**Four directories (disk layout):**

| Path | Purpose |
|---|---|
| `SKILL.md` | Main branch — constraints and primary workflow |
| `references/` | Heavy reference loaded on demand |
| `assets/` | Fixed assets consumed at runtime — agent prompts, templates, seed data, static config |
| `scripts/` | Deterministic tools the model invokes |

**Three loading levels (runtime behavior):**

1. **Metadata** (name + description) — always in context (~100 words)
2. **SKILL.md body** — in context when skill triggers (<500 lines ideal)
3. **references/** / **assets/** — loaded on demand; **scripts/** execute without loading

**Routing rule:** model needs it at trigger time → `SKILL.md`. Model needs it for specific tasks → `references/`. Output is deterministic → `scripts/`. Reusable fixed asset consumed by scripts or subagents → `assets/`.

**Why:** Context window is finite. A 1200-line SKILL.md means the model processes 1200 lines on every single invocation, even when it only needs 10% of them. Layering lets the model load only what the current task requires — SKILL.md for the core workflow, references/ for deep dives. This is the same principle as progressive enhancement in web development: base functionality always available, extras loaded as needed.

**TOC convention for large reference files (>300 lines):** a `## Table of Contents` heading followed by a multi-level unordered list of section names. Plain text — no anchor links. Agents read the text; they don't click links, so anchors are noise. The heading is required (not just a bare list) because it disambiguates the TOC from incidental lists elsewhere in the file. `check-skill.py` enforces this. `bad-example-*` files are exempt.

## #3 Determinism in code, uncertainty in AI

If a step has a deterministic output, it must be a script. `SKILL.md` describes when/why to invoke the script. The script does the work. AI judgment is reserved for genuinely uncertain decisions.

**Why:** LLMs are probabilistic. Ask one to count characters, parse CSV headers, or validate YAML structure, and you get an answer that's *usually* right — but not *always*. Scripts are deterministic: same input, same output, every time. When "usually right" isn't good enough (data validation, format conversion, counting), the script wins. When the task requires judgment, planning, or natural language (which examples to show, how to explain a concept), the AI wins. Routing work to the right executor eliminates an entire class of errors.

## #4 Tests must be done

Tests aren't optional, and they aren't satisfied by an empty `tests/` directory either. Before deployment, the Test loop must have actually been run. `check-skill.py` enforces this in two parts:

1. `tests/` has real content (evals.json, assertions, or manual checks). The `workspace/` subdirectory is run state, not test content — it doesn't count.
2. A `benchmark.json` exists under `tests/workspace/iteration-*/`, proving the loop ran at least through aggregate (init-workspace → spawn runs → grade → aggregate).

What goes in `tests/` depends on the skill: objective-output skills get evals + assertions (the Test loop produces these); subjective skills may need only a few manual checks. Either way, the loop must have been run. A skill that has never been tested will not pass check-skill.py.

**Why:** Skills modify agent behavior at a distance — a poorly written skill can make an agent worse, not better, and the author won't notice because they wrote the instructions and they make sense to *them*. A `tests/` directory you never exercised is just a folder. The benchmark.json requirement forces at least one "does this actually work?" run before shipping. Without it, you're shipping on faith.

## #5 Agent-friendly CLI

`#3` says deterministic work goes into scripts. `#5` says how those scripts must present themselves to the calling agent. Pattern: study [lark-cli](https://github.com/larksuite/cli) — every script Joe ships should follow these rules so the agent can use it confidently without bespoke handling per script. See [references/agent-friendly-cli-examples.md](agent-friendly-cli-examples.md) for deconstructed examples from lark-cli.

**Why:** Agents interact with scripts through stdout/stderr, not a GUI. When a script emits a raw Python traceback, the agent has to *read and interpret* free-form error text to figure out what went wrong — slow, unreliable, and impossible to automate. When a script returns a structured error envelope with `type`, `hint`, and `param`, the agent skips interpretation entirely: it knows the category of problem and the exact next action. The same applies to `--format json` — the agent shouldn't need to parse human-readable output with regex when it can get structured data directly. Agent-friendly CLI design eliminates the "reading comprehension" tax on every script invocation.

### 5.1 Three-layer command structure

Commands come in three layers. Pick the right one based on what the agent needs:

| Layer | Purpose | Example (lark-cli) | When to use |
|---|---|---|---|
| **Shortcut** | High-frequency task with smart defaults, named after intent (not API) | `lark-cli calendar +agenda` | 70% of agent invocations — the agent has an intent, not an API in mind |
| **API** | 1:1 mapping to a platform endpoint, named after the endpoint | `lark-cli calendar events instance_view` | Agent knows exactly which API to call and wants the canonical surface |
| **Raw** | Escape hatch for endpoints not yet covered | `lark-cli api GET /open-apis/calendar/v4/calendars` | Rare; when shortcut and API both don't apply |

A well-designed script exposes all three layers. Shortcuts are how the agent should call the script the vast majority of the time.

### 5.2 `--format` output envelope

Every script that produces data must support `--format` with at least these values:

- `json` — full structured data, suitable for piping to other tools
- `pretty` — human-readable, line-wrapped, colored where the terminal supports it
- `table` — column-aligned for human scanning

`json` is the default when stdout is not a TTY. `pretty` is the default when stdout is a TTY. This dual-default behavior means the same command works correctly in both interactive and pipe contexts.

### 5.3 Structured error envelope

Errors go to **stderr** as a structured envelope, not free-form text. The envelope must be parseable:

```
{
  "type": "validation_error",
  "subtype": "invalid_argument",
  "param": "--skill-path",
  "message": "skill-path must be a directory",
  "hint": "pass the absolute path to a skill directory, e.g. /home/me/skills/my-skill"
}
```

Fields:

- `type` + `subtype` — taxonomy the agent uses to decide next action (retry / fail / re-prompt user / etc.)
- `param` — names the specific user input that failed (only when applicable)
- `message` — one-line description, the human eye lands here first
- `hint` — actionable next step, the agent's parser lands here second

Never emit raw `fmt.Errorf("...")` strings as the only error output. The agent must be able to distinguish "I made a typo" from "the system is in a bad state" without reading the message.

### 5.4 stdout = data, stderr = everything else

Strict rule. Program output (data, results) goes to stdout. Progress, warnings, errors, hints, debug info, prompts go to stderr. Mixing them corrupts pipe chains (`script | jq` breaks if stderr is interleaved).

This is non-negotiable for agent piping. An agent doing `check_skill.py --format json | jq .errors` expects pure JSON on stdout.

## How these standards penetrate the official workflow

Each step of the official skill-creator workflow has a Joe standard reminder. See `SKILL.md` for the inline reminders. The standards are not an extra layer to consult separately — they modify what each step does.

## Helper scripts that encode the standards

- `scripts/check-skill.py` — Static structural lint (yaml frontmatter exists, SKILL.md < 500 lines, tests/ present, references resolve, scripts executable, scripts follow #5 conventions). Does NOT judge description content — that's the LLM's job.
- `scripts/scaffold-skill.sh` — Creates the four-layer directory skeleton for a new skill.
- `scripts/gen-eval.py` — Generates a starter `tests/evals/evals.json` with placeholder prompts.
- `scripts/validate-evals.py` — Validates `tests/evals/evals.json` schema (required fields, unique IDs, no placeholders).
- `scripts/validate-grading.py` — Validates `grading.json` schema (exact field names the viewer depends on: `text`, `passed`, `evidence`).
- `scripts/init-workspace.py` — Scaffolds workspace directory tree with `--runs-per-config N` (default 3) for statistical aggregation.
- `tests/test_check_skill.py` — Behavioral test suite for `check-skill.py`.
