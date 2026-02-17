#!/usr/bin/env bash
# Note validation hook — fires on PostToolUse:Write
# Checks that notes in docs/notes/ have required schema fields

set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# The file path is passed via CLAUDE_TOOL_INPUT
FILE_PATH="${CLAUDE_FILE_PATH:-}"

# Only validate files in the internal workspace
case "$FILE_PATH" in
  */docs/notes/*.md|*/docs/adr/*.md|*/self/*.md|*/ops/observations/*.md|*/ops/tensions/*.md)
    ;;
  *)
    exit 0
    ;;
esac

# Skip if file doesn't exist (deleted)
[ -f "$FILE_PATH" ] || exit 0

# Check for frontmatter
if ! head -1 "$FILE_PATH" | grep -q '^---$'; then
  echo "WARN: $FILE_PATH missing YAML frontmatter"
  exit 0
fi

# Check for description field (required for docs/notes/)
case "$FILE_PATH" in
  */docs/notes/*.md)
    if ! grep -q '^description:' "$FILE_PATH"; then
      echo "WARN: $FILE_PATH missing required 'description' field"
    fi
    ;;
esac
