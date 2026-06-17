# skill-creator++ Output Checks (Joe custom layer)

> **Status:** These are regression checks for skill-creator++'s own helper scripts (check-skill.py, scaffold-skill.sh, feedback.py, etc.), not a #4 requirement for skills created through it. #4 only requires that skills have a `tests/` directory. Run these when you've changed skill-creator++'s scripts and want to confirm they still behave correctly.

These checks verify the helper scripts Joe added on top of the official skill-creator.

## check-skill.py on a passing skill

- [ ] Run `python3 skills/skill-creator++/scripts/check-skill.py skills/skill-creator++` — expect exit code 0
- [ ] Run `python3 skills/skill-creator++/scripts/check-skill.py skills/skill-creator++ --verbose` — expect `OK` line at the end

## check-skill.py on a failing skill

- [ ] Create a temp skill missing `tests/`: `bash skills/skill-creator++/scripts/scaffold-skill.sh broken-skill "$TMPDIR"`
- [ ] Delete its `tests/` directory
- [ ] Run `python3 ... check-skill.py "$TMPDIR/broken-skill"` — expect exit code 1 and a `Joe #4` mention

- [ ] Create a temp skill missing the closing `---` frontmatter marker
- [ ] Run `python3 ... check-skill.py` on it — expect exit code 1 and a YAML frontmatter mention

## scaffold-skill.sh output

- [ ] Run `bash skills/skill-creator++/scripts/scaffold-skill.sh fresh-skill "$TMPDIR"`
- [ ] Verify the produced tree has: `SKILL.md`, `references/`, `assets/`, `scripts/`, `tests/`, `evals/`
- [ ] Verify `SKILL.md` has YAML frontmatter with `name:` and `description:` keys
- [ ] Re-running with the same name fails (no overwrite)

## gen-eval.py output

- [ ] Run `python3 skills/skill-creator++/scripts/gen-eval.py demo-skill /tmp/evals.json`
- [ ] Validate with `python3 -c "import json; json.load(...)"` — expect exit 0
- [ ] Confirm `skill_name` and `evals` array of length 5

## feedback.py round-trip

- [ ] `mkdir -p /tmp/iter-test/iteration-1`
- [ ] `python3 -m scripts.feedback show --iteration-dir /tmp/iter-test/iteration-1` — expect exit 0, JSON with empty `reviews` array
- [ ] `python3 -m scripts.feedback add --iteration-dir /tmp/iter-test/iteration-1 --run-id eval-1/with_skill/run-1 --feedback "missing labels"` — expect exit 0, `action: added`
- [ ] Re-run the same `add` command with `--feedback "fixed"` — expect `action: updated` (idempotent per run_id)
- [ ] `python3 -m scripts.feedback show --iteration-dir /tmp/iter-test/iteration-1` — expect 1 review with the updated text
- [ ] `python3 -m scripts.feedback add --iteration-dir /nonexistent --run-id x` — expect exit 2 and a structured error envelope on stderr
- [ ] `echo 'not json' > /tmp/iter-test/iteration-1/feedback.json && python3 -m scripts.feedback show --iteration-dir /tmp/iter-test/iteration-1` — expect exit 2 and `invalid_json` envelope

## aggregate_benchmark.py output

- [ ] Build a minimal workspace: `mkdir -p /tmp/bench/eval-1/{with_skill,without_skill}/run-1/outputs`
- [ ] Drop a `grading.json` with `summary: {pass_rate, passed, failed, total}` into each run-1 dir
- [ ] Drop a sample output file into each `outputs/` dir
- [ ] `python3 -m scripts.aggregate_benchmark /tmp/bench --skill-name demo` — expect exit 0
- [ ] Confirm `/tmp/bench/benchmark.md` has a Summary table AND a "Per-eval outputs" section listing the output files