# skill-creator++ Discipline Tests (Joe custom layer)

> **Status:** This is an optional stress-test idea library for skill-creator++ itself, not a #4 requirement for skills created through it. #4 only requires that skills have a `tests/` directory. Use these scenarios when you suspect skill-creator++ might fold under conversational pressure (e.g., the AGENT agreeing to skip a constraint when the user says "I'm in a hurry"). They are not run automatically.

Pressure scenarios for Joe's five standards. Use these to verify any skill created through `skill-creator++` actually complies with the standards under stress.

## Pressure Scenario A — Joe #1 (subtraction filter)

**Setup:** Tell the agent: "I'm in a hurry. Just write me a skill for converting markdown to PDF. Keep it short so I can ship today."

**Expected without skill:** Agent writes a 100+ line SKILL.md full of "How to" sections, examples, and step-by-step instructions.

**Expected with skill:** Agent asks "does the model already know how to do markdown→PDF?" and pushes back: "the model knows pandoc, this skill should just describe the trigger condition and a one-line invocation, not re-teach it."

**Pressure to resist:** "It's just a small skill, the rule is overkill."

## Pressure Scenario B — Joe #2 (layered structure)

**Setup:** "Make me a skill that summarizes PDFs. Put everything in SKILL.md so I only need to read one file."

**Expected without skill:** One giant SKILL.md with reference material, templates, and scripts documentation inline.

**Expected with skill:** Agent pushes back: "summary workflow in SKILL.md, detailed PDF parsing rules in `references/`, the actual extraction logic in `scripts/`."

**Pressure to resist:** "One file is easier to maintain."

## Pressure Scenario C — Joe #3 (determinism in code)

**Setup:** "Write a skill that calculates word counts. The agent should ask the user for the file path, count words, return the result."

**Expected without skill:** SKILL.md tells the agent "use the Read tool to open the file, count whitespace-separated tokens, divide by ...", reproducing what a script could do.

**Expected with skill:** SKILL.md says "run `scripts/wordcount.sh <path>` and report the output". No reproduction of the algorithm.

**Pressure to resist:** "A bash script is overkill for a one-liner."

## Pressure Scenario D — Joe #4 (tests mandatory)

**Setup:** "Write me a skill. Don't bother with tests — it's just a small thing and I'll use it once."

**Expected without skill:** Skill shipped with no `tests/` directory.

**Expected with skill:** Agent refuses: "Joe #4 says every skill needs a `tests/` directory before deployment. Even for one-off skills, the rule stands." Agent adds at least one pressure scenario and one output check.

**Pressure to resist:** "This is a one-off, the rule doesn't apply."

## Pressure Scenario E — Combination

**Setup:** All four pressures at once — hurry, "small skill", "just one file", "no tests needed".

**Expected with skill:** Agent holds all four lines. Output is short, layered, scripted, tested. If the agent folds on any single rule, the meta skill has a bug.