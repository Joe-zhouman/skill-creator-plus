#!/usr/bin/env bash
# scaffold-skill.sh — Create a new skill directory with the Joe four-class skeleton.
#
# Usage: scaffold-skill.sh <skill-name> [parent-dir]
#   skill-name   directory name for the new skill (lowercase, hyphens)
#   parent-dir   where to create it (default: ./skills/)
#
# Joe custom addition on top of the official skill-creator.
# Produces the four-layer structure (SKILL.md / references/ / assets/ / scripts/) plus tests/ and evals/.

set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <skill-name> [parent-dir]" >&2
  exit 2
fi

SKILL_NAME="$1"
PARENT_DIR="${2:-./skills}"

if [[ ! "$SKILL_NAME" =~ ^[a-z0-9][a-z0-9-]*[a-z0-9]$ ]]; then
  echo "Error: skill-name must be lowercase letters/digits/hyphens (got: $SKILL_NAME)" >&2
  exit 2
fi

TARGET="$PARENT_DIR/$SKILL_NAME"
if [[ -e "$TARGET" ]]; then
  echo "Error: $TARGET already exists" >&2
  exit 2
fi

mkdir -p "$TARGET/references"
mkdir -p "$TARGET/assets"
mkdir -p "$TARGET/scripts"
mkdir -p "$TARGET/tests"

# SKILL.md with YAML frontmatter and an empty body
cat > "$TARGET/SKILL.md" <<EOF
---
name: $SKILL_NAME
description: Use when TODO — replace this with a one-sentence description starting with "Use when".
---

# $SKILL_NAME

TODO: fill in the workflow after running this skill through skill-creator++.
EOF

touch "$TARGET/references/.gitkeep"
touch "$TARGET/assets/.gitkeep"
touch "$TARGET/tests/.gitkeep"

echo "Created $TARGET/"