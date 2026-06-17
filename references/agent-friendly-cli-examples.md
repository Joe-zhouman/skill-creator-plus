# Agent-Friendly CLI Examples — Deconstructed from lark-cli

Source: [larksuite/cli](https://github.com/larksuite/cli) (MIT, 14k stars)

lark-cli is a production-grade reference for #5 (Agent-friendly CLI). Below, each sub-rule of #5 is illustrated with a real lark-cli example and an explanation of why it matters for agents.

## Core design principle: errors tell the agent how to fix them

lark-cli doesn't just report failures — it returns actionable recovery paths. This principle runs deeper than any individual sub-rule. Every error response includes enough context for the agent to decide its next action without guessing:

- **Permission denied** → returns `permission_violations` (missing scopes), `console_url` (where to fix them), and `hint` (the exact command to run)
- **Confirmation required** → returns exit code 10 + `hint: "add --yes to confirm"` + `risk.action` so the agent can present the risk to the user
- **Version outdated** → returns `_notice.update` with `command: "lark-cli update"` — the agent doesn't need to look up how to update

The pattern: `type` tells the agent *what category* of problem, `hint` tells it *what to do next*, and domain-specific fields (`param`, `risk`, `permission_violations`, `console_url`) give it *the specifics it needs to act*. An agent that can't parse these has to fall back to reading free-form error text — slower, less reliable, and impossible to automate.

---

## 5.1 Three-layer command structure

lark-cli exposes three layers for the calendar domain:

```
# Shortcut — the agent says "show me today's calendar"
lark-cli calendar +agenda

# API — the agent knows exactly which endpoint to call
lark-cli calendar events instance_view \
  --params '{"calendar_id":"primary","start_time":"1700000000","end_time":"1700086400"}'

# Raw — escape hatch for endpoints not yet covered
lark-cli api GET /open-apis/calendar/v4/calendars
```

**Why this matters:** An agent usually has an intent ("check my schedule"), not an API name in mind. Shortcuts map intent → action with smart defaults. The agent only drops to API or Raw when the Shortcut doesn't cover the use case. This reduces prompt tokens (shorter commands) and error rate (fewer parameters to get wrong).

**How to apply:** When designing a script, ask: "What's the 70% case?" Make that the Shortcut with zero required parameters beyond the essential input. API and Raw layers are for the remaining 30%.

---

## 5.2 `--format` output envelope

```
lark-cli calendar +agenda --format json    # full structured data
lark-cli calendar +agenda --format pretty  # human-readable
lark-cli calendar +agenda --format table   # column-aligned
lark-cli calendar +agenda --format csv     # for spreadsheets
```

lark-cli defaults to `json` in pipe context and `pretty`/`table` on TTY — the same command "just works" whether the agent is piping to `jq` or a human is reading the terminal.

**Why this matters:** Agents parse JSON. Humans scan tables. A single `--format` flag lets the same command serve both without the agent needing to remember "use `-j` for this script, `--json` for that one."

**How to apply:** Every script that produces data must support at least `json`, `pretty`, and `table`. Default to `json` when stdout is not a TTY (pipe context), `pretty` when it is. This dual-default is non-negotiable — it means `script | jq .field` always works.

---

## 5.3 Structured error envelope — with recovery hints

### Example A: Permission denied (user identity)

```json
{
  "ok": false,
  "error": {
    "type": "permission_denied",
    "message": "Missing scope: calendar:calendar:readonly",
    "hint": "run: lark-cli auth login --scope \"calendar:calendar:readonly\"",
    "permission_violations": ["calendar:calendar:readonly"],
    "console_url": "https://open.feishu.cn/app/xxx/permission"
  }
}
```

The agent doesn't just learn "permission denied." It learns:
- **Which scope** is missing (`permission_violations`)
- **The exact command** to fix it (`hint`)
- **Where to go** if the scope isn't enabled yet (`console_url`)
- **That this is a user-identity issue**, not a server error (`type`)

For bot identity, the `hint` would instead say to visit `console_url` — because bots can't `auth login`.

### Example B: High-risk operation confirmation (exit code 10)

```json
{
  "ok": false,
  "error": {
    "type": "confirmation_required",
    "message": "drive +delete requires confirmation",
    "hint": "add --yes to confirm",
    "risk": {
      "level": "high-risk-write",
      "action": "drive +delete"
    }
  }
}
```

The agent's decision tree: exit 10 + `confirmation_required` → ask user → user agrees → retry with `--yes`. The `hint` gives the exact fix, `risk.action` tells the agent what to show the user.

### Example C: Version outdated (non-error notice)

```json
{
  "_notice": {
    "update": {
      "message": "new version available: v1.0.42 → v1.0.43",
      "command": "lark-cli update"
    }
  }
}
```

Not an error — the original command succeeded. But the agent is told *what to do* (`command`) and *why* (`message`), so it can offer to update after completing the user's request.

**Why this matters:** Without `hint`, the agent has to reason about the error from the message alone. "Permission denied" could mean: wrong identity, missing scope, expired token, or app not approved. The `type`/`subtype` taxonomy disambiguates; the `hint` skips the reasoning step entirely. This is faster, more reliable, and prevents the agent from taking the wrong recovery action (e.g., running `auth login` for a bot identity error).

**How to apply:** Every error response must include a `hint` field with an actionable next step. If multiple recovery paths exist, use `type`/`subtype` to distinguish them, and give the appropriate `hint` for each. The agent should never need to interpret free-form text to decide what to do.

---

## 5.4 stdout = data, stderr = everything else

lark-cli separates output cleanly:

```
# stdout — pure data (JSON by default)
$ lark-cli calendar +agenda --format json
{"items":[{"summary":"Team standup","start_time":"..."}]}

# stderr — progress, warnings, update notices
$ lark-cli calendar +agenda 2>/dev/null   # only data, no noise
{"items":[...]}
```

The `_notice.update` field (version update available) goes to stderr as a structured hint, never mixed into the data stream.

**Why this matters:** An agent doing `lark-cli calendar +agenda --format json | jq '.items[0]'` expects pure JSON on stdout. If a "Warning: token expires in 5 minutes" message is interleaved, `jq` breaks. Stderr is invisible to pipes by default, so progress/warnings/hints go there without corrupting data.

**How to apply:** `print(data, file=sys.stdout)` for results only. Everything else — logging, warnings, errors, hints, progress bars — goes to stderr. This is non-negotiable for composability.
