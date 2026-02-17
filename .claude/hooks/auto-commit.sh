#!/usr/bin/env bash
# Auto-commit hook — fires async on PostToolUse:Write
# Commits knowledge system files automatically

set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
FILE_PATH="${CLAUDE_FILE_PATH:-}"

# Only auto-commit internal workspace files
case "$FILE_PATH" in
  */docs/notes/*.md|*/docs/adr/*.md|*/arscontexta/self/*.md|*/arscontexta/ops/*.md|*/arscontexta/ops/*.json|*/arscontexta/ops/*.yaml|*/arscontexta/inbox/*.md|*/arscontexta/templates/*.md|*/arscontexta/manual/*.md)
    ;;
  *)
    exit 0
    ;;
esac

[ -f "$FILE_PATH" ] || exit 0

cd "$PROJECT_ROOT"

# Get path relative to project root
REL_PATH="${FILE_PATH#$PROJECT_ROOT/}"

# Stage and commit
git add "$REL_PATH" 2>/dev/null || exit 0
git diff --cached --quiet && exit 0

BASENAME=$(basename "$REL_PATH")
git commit -m "Auto: $BASENAME" --no-verify -q 2>/dev/null || true
