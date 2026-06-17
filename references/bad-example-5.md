# Bad Example #5 — Agent-hostile CLI scripts

This file demonstrates what happens when scripts ignore #5 (agent-friendly CLI).
Each example shows a script that "works for humans" but breaks in an agent pipeline.

---

## Example 1: No `--format`, mixed stdout/stderr

```python
#!/usr/bin/env python3
"""merge-csv.py — Merge multiple CSV files."""

import csv
import sys

if len(sys.argv) < 3:
    print("Usage: merge-csv.py file1.csv file2.csv ... -o output.csv")
    sys.exit(1)

files = []
output = "merged.csv"
args = sys.argv[1:]
i = 0
while i < len(args):
    if args[i] == "-o":
        output = args[i + 1]
        i += 2
    else:
        files.append(args[i])
        i += 1

print(f"Merging {len(files)} files...")
all_rows = []
for f in files:
    with open(f) as fh:
        reader = csv.DictReader(fh)
        all_rows.extend(list(reader))
        print(f"  Read {f}: {len(all_rows)} rows so far")

with open(output, "w", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=all_rows[0].keys())
    writer.writeheader()
    writer.writerows(all_rows)

print(f"Done! Wrote {len(all_rows)} rows to {output}")
```

**What goes wrong when an agent calls this:**

1. **No `--format json`** — the agent can't parse "Merging 3 files..." or "Done! Wrote 450 rows". It gets free-form English on stdout instead of structured data. If the agent pipes this to `jq`, it breaks.

2. **Progress mixed into stdout** — `print(f"Read {f}: {len(all_rows)} rows so far")` goes to stdout. If the agent does `merge-csv.py a.csv b.csv -o out.csv | jq .`, the progress lines corrupt the pipe. The agent has no way to extract just the result.

3. **Missing output file** — if the `-o` flag is missing or the path is wrong, the script prints `IndexError: list index out of range` (a raw Python traceback). The agent sees a 15-line stack trace instead of `"param": "-o", "hint": "specify output path with -o"`. It can't tell "I forgot -o" from "the disk is full".

4. **Empty input** — if `all_rows` is empty, `all_rows[0].keys()` throws `IndexError` and the agent gets another raw traceback. No `type`, no `hint`, no recovery path.

---

## Example 2: Errors as free-form text, no envelope

```python
#!/usr/bin/env python3
"""filter-csv.py — Filter rows by column value."""

import csv
import sys

filename = sys.argv[1]
column = sys.argv[2]
value = sys.argv[3]

with open(filename) as f:
    reader = csv.DictReader(f)
    if column not in reader.fieldnames:
        print(f"Error: column '{column}' not found. Available columns: {', '.join(reader.fieldnames)}")
        sys.exit(1)
    matched = [row for row in reader if row[column] == value]

print(f"Found {len(matched)} rows where {column}={value}")
for row in matched:
    print(",".join(row.values()))
```

**What goes wrong:**

1. **Error on stdout** — `print(f"Error: ...")` goes to stdout, not stderr. If the agent pipes output, the error message is mixed with data. `filter-csv.py data.csv status active | head` produces "Error: column 'stats' not found..." as the first line of "data".

2. **No structured envelope** — the agent sees `Error: column 'stats' not found. Available columns: name, email, status`. It has to *read and interpret* this English sentence to figure out it made a typo. With a structured envelope, it would get `{"type": "validation_error", "param": "--column", "hint": "did you mean 'status'?"}` — no reading required.

3. **Data as CSV on stdout** — the matched rows are printed as raw CSV lines. No `--format json` option. The agent can't parse this reliably (what if a value contains a comma?). It's `--format json` or nothing, and the script offers nothing.

4. **No `--format` at all** — "Found 42 rows where status=active" is human-readable, but an agent can't extract the count programmatically. It would need regex. With `--format json`, it gets `{"count": 42, "rows": [...]}` directly.

---

## The fix (what #5 requires)

Both scripts should:

- Support `--format json|pretty|table`, defaulting to `json` in pipe context
- Emit data to stdout, everything else to stderr
- Return structured error envelopes on stderr:
  ```json
  {"type": "validation_error", "subtype": "invalid_argument", "param": "--column", "message": "column 'stats' not found", "hint": "available columns: name, email, status — did you mean 'status'?"}
  ```
- Let the agent distinguish "I made a typo" from "the file doesn't exist" from "the script has a bug" without reading error messages
