---
name: skill-creator-plus
description: Create new skills, or modify and improve existing ones. Use when users want to create a skill from scratch, edit or optimize an existing skill, run evals to verify a skill works, or optimize a skill's description for better triggering accuracy.
---

> **This skill is under active iteration.** When you hit friction — a script that doesn't work as documented, a path that's wrong, an instruction that misled you, an edge case the workflow doesn't handle — **don't just work around it**. Append a short note to `KNOWN_ISSUES.md` (skill root) describing: what you did, what you expected, what actually happened, and a one-line fix idea if you have one. The next iteration uses that file as its punch list.

# Skill Creator

## When (and what to do)

Match the user's request to one of two functions:

| User wants to... | Workflow to use | Section below |
|---|---|---|
| **Create** a new skill from scratch | Capture Intent → Write → Test → Improve loop | [Creating a skill](#creating-a-skill) |
| **Improve** an existing skill (whether just drafted or already in use) | Test (against current version) → Improve loop | [Improving the skill](#improving-the-skill) |

Both functions share the same test-and-improve loop. The only difference is whether you start from a draft (Create) or an installed skill (Improve). Testing isn't a standalone activity here — you run evals to see what to improve, then improve.

## How (general shape)

Both functions ride on the same machinery: a SKILL.md (or draft) + evals + scripts. The difference is where you enter the loop:

- **Create** enters at Capture Intent, runs through Test → Improve, optionally does Description Optimization at the end
- **Improve** enters at Test Cases (using the existing skill as baseline), runs the Improve loop until it converges

Flexibility: the user may have a draft already (skip Capture Intent), or want only one run without iteration (stop after the first Test pass). Jump in where they are.

## Joe's Standards for a well-written skill

There is no definitive answer to what makes a good skill. To keep the quality of generated skills in check, Joe set five standards: #1 subtraction filter, #2 layered structure + progressive disclosure, #3 determinism in code, #4 tests mandatory, #5 agent-friendly CLI. Full text in [references/joe-standard.md](references/joe-standard.md); deconstructed examples from lark-cli in [references/agent-friendly-cli-examples.md](references/agent-friendly-cli-examples.md). Reminders appear inline below.

## Creating a skill

### Capture Intent

Start by understanding the user's intent. The current conversation might already contain a workflow the user wants to capture (e.g., they say "turn this into a skill"). If so, extract answers from the conversation history first — the tools used, the sequence of steps, corrections the user made, input/output formats observed. The user may need to fill the gaps, and should confirm before proceeding to the next step.

1. What should this skill enable the AGENT to do?
2. When should this skill trigger? (what user phrases/contexts)
3. What's the expected output format?
4. Should we set up test cases to verify the skill works? Skills with objectively verifiable outputs (file transforms, data extraction, code generation, fixed workflow steps) benefit from test cases. Skills with subjective outputs (writing style, art) often don't need them. Suggest the appropriate default based on the skill type, but let the user decide.

> **Joe #1 — subtraction filter:** before writing any sentence, ask "does the model already know this?" Known → skip. Unknown → write freely. Uncertain → default to writing (see [references/joe-standard.md](references/joe-standard.md#1-subtraction-filter)).

### Interview and Research

Proactively ask questions about edge cases, input/output formats, example files, success criteria, and dependencies. Wait to write test prompts until you've got this part ironed out.

Check available MCPs - if useful for research (searching docs, finding similar skills, looking up best practices), research in parallel via subagents if available, otherwise inline. Come prepared with context to reduce burden on the user.

### Write the SKILL.md

If you scaffolded with `scaffold-skill.sh`, the script wrote a placeholder `SKILL.md` via shell heredoc — the Write tool doesn't know about it, so your first edit to `SKILL.md` will be rejected with "must Read first". Read the placeholder once, then overwrite.

Based on the user interview, fill in these components:

- **name**: Skill identifier
- **description**: When to trigger, what it does. This is the primary triggering mechanism - include both what the skill does AND specific contexts for when to use it. All "when to use" info goes here, not in the body. Note: the agent has a tendency to "undertrigger" skills -- to not use them when they'd be useful. To combat this, please make the skill descriptions a little bit "pushy". So for instance, instead of "How to build a simple fast dashboard to display internal Cloudflare data.", you might write "How to build a simple fast dashboard to display internal Cloudflare data. Make sure to use this skill whenever the user mentions dashboards, data visualization, internal metrics, or wants to display any kind of company data, even if they don't explicitly ask for a 'dashboard.'"
- **compatibility**: Required tools, dependencies (optional, rarely needed)
- **the rest of the skill :)**

### Skill Writing Guide

#### Anatomy of a Skill

```
skill-name/
├── SKILL.md          — constraints + primary workflow (#1: only what the model can't infer)
│   ├── YAML frontmatter (name, description required)
│   └── Markdown instructions
├── scripts/          — deterministic tools (#3); agent-friendly CLI (#5)
├── references/       — heavy docs loaded on demand (#2)
├── assets/           — fixed assets consumed at runtime: agent prompts, templates, seed data (#2)
└── tests/            — mandatory before deployment (#4)
```

Run `$SKILL_CREATOR/scripts/scaffold-skill.sh <skill-name> [parent-dir]` to generate this skeleton (`parent-dir` defaults to `./skills/`).

#### Progressive Disclosure

Three loading levels (#2):
1. **Metadata** (name + description) — always in context (~100 words)
2. **SKILL.md body** — in context when skill triggers (<500 lines ideal)
3. **references/** / **assets/** — loaded on demand; **scripts/** execute without loading

Word counts are approximate — go longer if needed.

**Key patterns:**
- Keep SKILL.md under 500 lines; if approaching this limit, add hierarchy with pointers to where to go next.
- Reference files clearly from SKILL.md with guidance on when to read them.
- For large reference files (>300 lines), include a table of contents.

**Domain organization**: When a skill supports multiple domains/frameworks, organize by variant:
```
cloud-deploy/
├── SKILL.md (workflow + selection)
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```
The AGENT reads only the relevant reference file.

#### Structural lint: `check-skill.py`

The constraints above are not advisory — they are enforced by `scripts/check-skill.py`. Run it before every commit:

```bash
python3 $SKILL_CREATOR/scripts/check-skill.py <skill-path>              # pretty (TTY) or json (pipe)
python3 $SKILL_CREATOR/scripts/check-skill.py <skill-path> --format json # machine-readable
python3 $SKILL_CREATOR/scripts/check-skill.py <skill-path> --verbose     # log checks to stderr
```

**Hard checks** (exit 1 on failure):
- SKILL.md exists with valid YAML frontmatter (`---` open/close)
- YAML frontmatter contains both `name` and `description`
- SKILL.md ≤ 500 lines
- All relative paths referenced from SKILL.md resolve to existing files
- All `.sh`/`.py` files in `scripts/` are executable
- `tests/` exists with test content (workspace/ alone doesn't count) (#4)
- `tests/workspace/iteration-*/benchmark.json` exists — proves the Test loop has been run at least once (#4)

**Soft checks** (warnings to stderr, never fail):
- Reference files >300 lines without a table of contents — add a `## Table of Contents` heading followed by a multi-level plain-text list of sections (no anchor links — agents read the text, they don't click). `bad-example-*` files are exempt.

#### Writing Patterns

**Defining output formats:**
```markdown
## Report structure
ALWAYS use this exact template:
# [Title]
## Executive summary
## Key findings
## Recommendations
```

**Examples pattern** — include examples when the expected transformation isn't obvious:
```markdown
## Commit message format
**Example 1:**
Input: Added user authentication with JWT tokens
Output: feat(auth): implement JWT-based authentication
```

#### Writing Style

Explain the **why** behind instructions. Trust the model's theory of mind — if you give a good reason, it generalizes better than a rigid MUST. Write a draft, then reread with fresh eyes.

### Common Mistakes

These anti-patterns apply across create, modify, and improve workflows.

**Writing a tutorial, not a skill (#1 + #2).** The anti-patterns:

- **"Overview" / "Core Concepts" sections** — the model already knows the library. This is reference documentation, not a skill.
- **Cataloging all options** — listing every plot type, every styling method. A skill should encode *judgment*, not *reference data*.
- **Long code examples for things the model can do itself** — it needs to know *when* and *why*, not *how*.
- **"Additional Resources" linking to official docs** — the model knows where to find them. Burns context for zero gain.

The fix: apply #1. What remains should be constraints, judgments, and non-obvious gotchas.

**Using AI for deterministic work (#3).** "Count the r's in strawberry" has one correct answer. Writing 40 lines of step-by-step instructions is asking the model to do something it's bad at when a one-line script does it perfectly. If the output has one right answer, it's a script.

**Agent-hostile script interfaces (#5).** Scripts that print free-form text to stdout, return raw Python tracebacks on error, and offer no `--format` flag. The agent can't tell "I mistyped a parameter" from "the file doesn't exist" from "the script crashed" — and can't pipe output to other tools.

If these patterns aren't clear from the descriptions above, read the full deconstructions:
- [references/bad-example-1.md](references/bad-example-1.md) — #1 + #2 violation: a matplotlib skill that's a tutorial, with 360 lines that belong in references/
- [references/bad-example-3.md](references/bad-example-3.md) — #3 violation: a char-count skill that should be a script
- [references/bad-example-5.md](references/bad-example-5.md) — #5 violation: scripts with no --format, no error handling, no structured output — the AGENT gets raw tracebacks on failure

> **Joe #1, #2, #3, #4, #5** apply throughout. See [references/joe-standard.md](references/joe-standard.md).

## Running and evaluating test cases

> **Joe #4 — tests must be done:** 

This is the shared test-and-review loop used by both Create and Improve. When you reach this section (either fresh from writing a draft, or coming back to an existing skill), run it end to end — don't stop partway through. Do NOT use `/skill-test` or any other testing skill.

**Two different "root" directories are in play.** Getting them confused is the most common source of friction in this loop:

- **The target skill's root** — the skill you're creating or improving. Your shell's working directory should be here. All `tests/workspace/evals.json`, `SKILL.md`, `references/...` references below resolve against this directory. If you're not in it, `cd` into it first.
- **skill-creator-plus's own root** — where *this* skill lives. The scripts that drive the test loop (`gen-eval.py`, `init-workspace.py`, `validate-evals.py`, `aggregate_benchmark.py`, `feedback.py`, `check-skill.py`, `validate-grading.py`, `run_one_iter.py`, `improve_description.py`) all live in **skill-creator-plus's** `scripts/`, NOT the target skill's `scripts/`. Invoke them by absolute path so the shell finds them regardless of your cwd. The default install location is `~/.claude/skills/skill-creator-plus/` — if that's where you are reading this from, use it directly:

  ```bash
  SKILL_CREATOR=~/.claude/skills/skill-creator-plus
  python3 $SKILL_CREATOR/scripts/<script>.py <args>
  ```

  If you're reading this from somewhere else (fork, symlink, non-standard install), set `SKILL_CREATOR` to the directory containing the SKILL.md you're currently reading.

### Step 0: Draft test cases

All prompts here are should-trigger — cases that genuinely need the skill and produce an output you can grade. 

First generate the starter `evals.json` with `python3 scripts/gen-eval.py <skill-name> tests/workspace/evals.json`, then fill in with 3 realistic prompts that would trigger the skill:

Three slots is the default — pick prompts a real user would actually say, covering different phrasings and at least one edge case. Share them with the user: [you don't have to use this exact language] "Here are the test cases I'd like to try. Do these look right, or do you want to add more?" Add or remove slots as you see fit.

Filling the `expectations` array is **optional at this step** — if you already have a clear sense of what each test case should verify, write them now. If not, leave the array empty and you'll draft them in Step 3 while the runs are in progress. Either flow is fine; the starter has the `expectations` field there to use if you want it, not as a requirement. Validate with `python3 $SKILL_CREATOR/scripts/validate-evals.py tests/workspace/evals.json` before continuing.

### Step 1: Setup workspace

Initialize the workspace before spawning runs:

```bash
python3 $SKILL_CREATOR/scripts/init-workspace.py --skill-path . --evals tests/workspace/evals.json [--iteration N] [--runs-per-config N]
```

This creates `tests/workspace/` (gitignored — local run state, like node_modules). Default is 3 runs per configuration (with-skill and without-skill), producing `run-1/` through `run-3/` under each config directory. LLM output is probabilistic — multiple runs give mean ± stddev, not a single anecdotal result. For iteration 2+, pass `--iteration 2` — it adds to the existing workspace without touching previous iterations.

```
iteration-N/
└── eval-ID/
    ├── eval_metadata.json
    ├── with_skill/
    │   ├── run-1/outputs/
    │   ├── run-2/outputs/
    │   └── run-3/outputs/   ← number of runs = --runs-per-config (default 3)
    └── without_skill/
        ├── run-1/outputs/
        ├── run-2/outputs/
        └── run-3/outputs/
```

### Step 2: Spawn all runs (with-skill AND baseline) in the same turn

For each test case, spawn subagents for all runs in the same turn — the total is `evals × runs_per_config × 2` subagent tasks (with-skill + baseline). Don't spawn with-skill runs first and come back for baselines later. Launch everything at once so it all finishes around the same time.

**With-skill run (repeat for run-1, run-2, run-3):**

The placeholder fields are filled by you (the orchestrating agent) before dispatching. Concretely:

- **Skill path**: absolute path to the target skill's root — the same skill your cwd is in. For baseline runs (below) this becomes "none" or the snapshot path instead.
- **Task / Input files / Outputs to save**: copied from the eval prompt and your judgment.
- **Save outputs to**: absolute path. Pattern is `<target-skill-root>/tests/workspace/iteration-<N>/eval-<ID>/<config>/run-<M>/outputs/`. `<N>` is the iteration number you passed to init-workspace, `<ID>` is the eval's `id` field from evals.json, `<config>` is `with_skill` or `without_skill`, `<M>` is the run number 1..runs_per_config.

```
Execute this task:
- Skill path: <absolute path to the target skill root>
- Task: <eval prompt verbatim>
- Input files: <eval files if any, or "none">
- Save outputs to: <absolute path>/tests/workspace/iteration-<N>/eval-<ID>/with_skill/run-<M>/outputs/
- Outputs to save: <what the user cares about — e.g., "the .docx file", "the final CSV">
```

**Baseline run** (same prompt, repeated for each run-M):
- **Creating a new skill**: no skill at all. Same prompt, no skill path, save to `without_skill/run-<M>/outputs/`.
- **Improving an existing skill**: the old version. Before editing, snapshot the skill (`cp -r . tests/workspace/skill-snapshot/`), then point the baseline subagent at the snapshot. Save to `old_skill/run-<M>/outputs/`.

`eval_metadata.json` for each test case is already generated by `init-workspace.py` (expectations empty). Update the `eval_name` field to be descriptive — not just "eval-0". If this iteration uses new or modified eval prompts, re-run `init-workspace.py` with the updated evals.json.

### Step 3: While runs are in progress, finalize expectations

Don't just wait for the runs to finish — use this window productively. If you deferred expectations in Step 0, draft them now. If you filled them in Step 0, review them against the actual prompts and refine — early drafts often miss things you notice once the runs start producing output.

Explain each expectation to the user so they can sanity-check the criteria before grading happens.

Good expectations are objectively verifiable and have descriptive names — they should read clearly in `benchmark.md` so someone glancing at the results immediately understands what each one checks. Subjective skills (writing style, design quality) are better evaluated qualitatively — don't force expectations onto things that need human judgment.

Update the `eval_metadata.json` files and `tests/workspace/evals.json` with the expectations once finalized. Also explain to the user what they'll see in the review — both the qualitative outputs (which you'll walk them through) and the quantitative benchmark.

### Step 4: As runs complete, fill in timing data

Each run directory already has a scaffolded `timing.json` with two fields. When a subagent task completes, you receive a notification with `total_tokens` and `duration_ms` — fill those in immediately:

```json
{
  "total_tokens": 84852,
  "total_duration_seconds": 23.3
}
```

(`total_duration_seconds` = `duration_ms` / 1000.) This is the only opportunity to capture this data — it comes through the task notification and isn't persisted elsewhere. Process each notification as it arrives rather than trying to batch them.

### Step 5: Grade, aggregate, and review with the user

Once all runs are done:

1. **Grade each run** — spawn a grader subagent (or grade inline) that reads `$SKILL_CREATOR/assets/agents/grader.md` and evaluates each expectation against the outputs. Grade each run independently (run-1, run-2, run-3 each get their own `grading.json` in the run directory). Validate with `python3 $SKILL_CREATOR/scripts/validate-grading.py <grading.json>` before proceeding — downstream scripts depend on exact field names (`text`, `passed`, `evidence`) and the validator catches mismatches. For expectations that can be checked programmatically, write and run a script rather than eyeballing it — scripts are faster, more reliable, and can be reused across runs and iterations.

2. **Aggregate into benchmark** — run the aggregation script from the target skill's root (your cwd):
   ```bash
   python3 $SKILL_CREATOR/scripts/aggregate_benchmark.py tests/workspace/iteration-N --skill-name my-skill
   ```
   Replace `my-skill` with the actual skill name (it gets written into `benchmark.md`'s title — if you skip `--skill-name`, the title shows `<skill-name>` literally). This produces `benchmark.json` and `benchmark.md` (both inside the iteration dir). The Markdown has a summary table (pass_rate, time, tokens with mean ± stddev and delta) plus a per-eval section listing each run's output file paths — use those paths to open outputs directly during the review. The script treats the first configuration it encounters as primary and the second as baseline — put `with_skill` directories before `without_skill` so the delta is computed in the right direction.

3. **Do an analyst pass** — read the benchmark data and surface patterns the aggregate stats might hide. See `$SKILL_CREATOR/assets/agents/analyzer.md` (the "Analyzing Benchmark Results" section) for what to look for — things like expectations that always pass regardless of skill (non-discriminating), high-variance evals (possibly flaky), and time/token tradeoffs.

4. **Walk the user through the results in conversation** — open `benchmark.md`, then for each eval:
   - Tell the user the pass rate and which expectations failed
   - Point them at the output file path (from the per-eval section of `benchmark.md`) to open themselves
   - Ask: "How does this output look? Any specific feedback?"
   - Record their answer with `feedback.py`:
     ```bash
     python3 $SKILL_CREATOR/scripts/feedback.py add \
       --iteration-dir <workspace>/iteration-N \
       --run-id eval-<ID>/<config>/run-<M> \
       --feedback "<their text>"
     ```
   Empty feedback (user says "looks fine") is recorded as an empty string — `--feedback` defaults to empty, so you can omit it.

   For iteration 2+, read the previous iteration's feedback first so you can ask "last time you said X about this — still an issue?":
   ```bash
   python3 $SKILL_CREATOR/scripts/feedback.py show --iteration-dir <workspace>/iteration-<N-1>
   ```

5. **Tell the user** you've finished collecting feedback and are ready to improve the skill. Empty feedback across the board means everything looked good — you can suggest stopping.

---

## Improving the skill

> **Joe #1, #2, #3, #5:** Re-run subtraction filter on every revision. Move growing detail to `references/`. Promote deterministic steps to scripts. Ensure new/changed scripts follow agent-friendly CLI conventions (see [references/joe-standard.md](references/joe-standard.md)).

This is the heart of the loop. You've run the test cases, the user has reviewed the results, and now you need to make the skill better based on their feedback.

**Prerequisite check:** If the skill was not created through this workflow (e.g., an external skill the user brought in), it may lack `tests/workspace/evals.json` and the workspace structure. Before entering the iteration loop, check — if missing, scaffold them: `$SKILL_CREATOR/scripts/scaffold-skill.sh <skill-name> [parent-dir]` for the directory skeleton, `$SKILL_CREATOR/scripts/gen-eval.py` for starter evals, then write realistic test prompts and run `$SKILL_CREATOR/scripts/init-workspace.py` before spawning runs.

### How to think about improvements

1. **Generalize from the feedback.** The big picture thing that's happening here is that we're trying to create skills that can be used a million times (maybe literally, maybe even more who knows) across many different prompts. Here you and the user are iterating on only a few examples over and over again because it helps move faster. The user knows these examples in and out and it's quick for them to assess new outputs. But if the skill you and the user are codeveloping works only for those examples, it's useless. Rather than put in fiddly overfitty changes, or oppressively constrictive MUSTs, if there's some stubborn issue, you might try branching out and using different metaphors, or recommending different patterns of working. It's relatively cheap to try and maybe you'll land on something great.

2. **Keep the prompt lean.** Remove things that aren't pulling their weight. Make sure to read the transcripts, not just the final outputs — if it looks like the skill is making the model waste a bunch of time doing things that are unproductive, you can try getting rid of the parts of the skill that are making it do that and seeing what happens.

3. **Explain the why.** Try hard to explain the **why** behind everything you're asking the model to do. Today's LLMs are *smart*. They have good theory of mind and when given a good harness can go beyond rote instructions and really make things happen. Even if the feedback from the user is terse or frustrated, try to actually understand the task and why the user is writing what they wrote, and what they actually wrote, and then transmit this understanding into the instructions. If you find yourself writing ALWAYS or NEVER in all caps, or using super rigid structures, that's a yellow flag — if possible, reframe and explain the reasoning so that the model understands why the thing you're asking for is important. That's a more humane, powerful, and effective approach.

4. **Look for repeated work across test cases.** Read the transcripts from the test runs and notice if the subagents all independently wrote similar helper scripts or took the same multi-step approach to something. If all 3 test cases resulted in the subagent writing a `create_docx.py` or a `build_chart.py`, that's a strong signal the skill should bundle that script. Write it once, put it in `scripts/`, and tell the skill to use it. This saves every future invocation from reinventing the wheel.

This task is pretty important (we are trying to create billions a year in economic value here!) and your thinking time is not the blocker; take your time and really mull things over. I'd suggest writing a draft revision and then looking at it anew and making improvements. Really do your best to get into the head of the user and understand what they want and need.

### The iteration loop

After improving the skill:

1. Apply your improvements to the skill
2. Initialize the new iteration: `python3 $SKILL_CREATOR/scripts/init-workspace.py --skill-path . --evals tests/workspace/evals.json --iteration <N+1>`. This adds to the existing workspace without touching previous iterations.
3. Rerun all test cases into the new iteration directory, including baseline runs. If you're creating a new skill, the baseline is always `without_skill` (no skill) — that stays the same across iterations. If you're improving an existing skill, use your judgment on what makes sense as the baseline: the original version the user came in with, or the previous iteration.
4. Run Step 5 again on the new iteration. When walking the user through outputs, first show the previous iteration's feedback via `python3 $SKILL_CREATOR/scripts/feedback.py show --iteration-dir <workspace>/iteration-<N>` so you can ask whether old issues are resolved.
5. Wait for the user to review and tell you they're done
6. Read the new feedback, improve again, repeat

Keep going until:
- The user says they're happy
- The feedback is all empty (everything looks good)
- You're not making meaningful progress

---

## Advanced: Blind comparison

For situations where you want a more rigorous comparison between two versions of a skill (e.g., the user asks "is the new version actually better?"), there's a blind comparison system. Read `assets/agents/comparator.md` and `assets/agents/analyzer.md` for the details. The basic idea is: give two outputs to an independent agent without telling it which is which, and let it judge quality. Then analyze why the winner won.

This is optional, requires subagents, and most users won't need it. The human review loop is usually sufficient.

---

## Description Optimization

> **Joe #1 — subtraction filter:** Description is a triggering signal, not a tutorial summary. Write "Use when X" with concrete symptoms; skip what the model already infers (see [references/joe-standard.md](references/joe-standard.md#1-subtraction-filter)).

The description field in SKILL.md frontmatter is the primary mechanism that determines whether the AGENT invokes a skill. After creating or improving a skill, offer to optimize the description for better triggering accuracy.

### Step 1: Generate trigger eval queries

Create 20 eval queries — a mix of should-trigger and should-not-trigger. Save as JSON:

```json
[
  {"query": "the user prompt", "should_trigger": true},
  {"query": "another prompt", "should_trigger": false}
]
```

The queries must be realistic and something an AGENT user would actually type. Not abstract requests, but requests that are concrete and specific and have a good amount of detail. For instance, file paths, personal context about the user's job or situation, column names and values, company names, URLs. A little bit of backstory. Some might be in lowercase or contain abbreviations or typos or casual speech. Use a mix of different lengths, and focus on edge cases rather than making them clear-cut (the user will get a chance to sign off on them).

Bad: `"Format this data"`, `"Extract text from PDF"`, `"Create a chart"`

Good: `"ok so my boss just sent me this xlsx file (its in my downloads, called something like 'Q4 sales final FINAL v2.xlsx') and she wants me to add a column that shows the profit margin as a percentage. The revenue is in column C and costs are in column D i think"`

For the **should-trigger** queries (8-10), think about coverage. You want different phrasings of the same intent — some formal, some casual. Include cases where the user doesn't explicitly name the skill or file type but clearly needs it. Throw in some uncommon use cases and cases where this skill competes with another but should win.

For the **should-not-trigger** queries (8-10), the most valuable ones are the near-misses — queries that share keywords or concepts with the skill but actually need something different. Think adjacent domains, ambiguous phrasing where a naive keyword match would trigger but shouldn't, and cases where the query touches on something the skill does but in a context where another tool is more appropriate.

The key thing to avoid: don't make should-not-trigger queries obviously irrelevant. "Write a fibonacci function" as a negative test for a PDF skill is too easy — it doesn't test anything. The negative cases should be genuinely tricky.

### Step 2: Review the queries with the user

Show the eval set to the user as a Markdown list (no HTML, no template). Read it back, let them edit queries, toggle should-trigger, add or remove entries. Bad queries lead to bad descriptions, so this review matters.

### Step 3: Iterate one round at a time

Each round: run the trigger test, read the result, ask the user.

```bash
python3 $SKILL_CREATOR/scripts/run_one_iter.py \
  --eval-set <path-to-trigger-eval.json> \
  --skill-path <path-to-skill> \
  --iteration 1 \
  --output-dir tests/workspace/description-optimization
```

This writes `iter-N.md` (read this) and `iter-N.json` (for parsing the pass rate) to the output dir. Each query runs 3 times by default to get a stable trigger rate. Use the model ID from your system prompt via `--model` so the test matches what the user actually experiences.

After each round, read the Markdown and ask the user something like: "Pass rate is X%. The failing queries are Y. Should I tweak the description and run another round, or stop here?"

If continuing, edit the description based on the user's feedback. Three options for producing the new description, in order of preference:

1. **You draft it** — read the failing queries in `iter-N.md`, infer what intent the description is missing or over-claiming, rewrite. Fastest, keeps you in the loop with the user.
2. **Ask the user** — sometimes they have a clear idea of the phrasing that should trigger (or not trigger).
3. **Call `improve_description.py`** — optional helper that calls `claude -p` with a tuned prompt (don't overfit, 100-200 words, imperative voice). Useful when you're stuck or want a second-opinion draft:
   ```bash
   python3 $SKILL_CREATOR/scripts/improve_description.py \
     --eval-results <output-dir>/iter-N.json \
     --skill-path <path-to-skill> \
     --model <model-id> \
     [--history <output-dir>/history.json]
   ```
   It prints a candidate description + updated history as JSON. Always show the candidate to the user before applying — don't auto-apply.

Whatever the source, update SKILL.md's frontmatter with the new description, then run the next round with `--iteration N+1`. Stop when the user is satisfied or the pass rate plateaus across rounds.

### How skill triggering works

Understanding the triggering mechanism helps design better eval queries. Skills appear in the AGENT's `available_skills` list with their name + description, and the AGENT decides whether to consult a skill based on that description. The important thing to know is that the AGENT only consults skills for tasks it can't easily handle on its own — simple, one-step queries like "read this PDF" may not trigger a skill even if the description matches perfectly, because the AGENT can handle them directly with basic tools. Complex, multi-step, or specialized queries reliably trigger skills when the description matches.

This means your eval queries should be substantive enough that the AGENT would actually benefit from consulting a skill. Simple queries like "read file X" are poor test cases — they won't trigger skills regardless of description quality.

### Step 4: Apply the result

Once the user is happy with a round's description, update the skill's SKILL.md frontmatter. Show the user before/after and report the final pass rate.

---

## Reference files

- `assets/agents/grader.md` — How to evaluate expectations against outputs
- `assets/agents/comparator.md` — How to do blind A/B comparison between two outputs
- `assets/agents/analyzer.md` — How to analyze why one version beat another
- `references/schemas.md` — JSON structures for evals.json, grading.json, etc.
- `references/joe-standard.md` — Joe's five custom standards (see top of this file)
