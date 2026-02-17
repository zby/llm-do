#!/usr/bin/env bash
# Session capture hook — fires on Stop
# Archives the current session state

set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
SESSION_FILE="$PROJECT_ROOT/ops/sessions/current.json"

if [ ! -f "$SESSION_FILE" ]; then
  exit 0
fi

# Update last activity timestamp
if command -v jq &>/dev/null; then
  TMP=$(mktemp)
  jq --arg ts "$(date -Iseconds)" '.last_activity = $ts' "$SESSION_FILE" > "$TMP" && mv "$TMP" "$SESSION_FILE"
fi

# Archive with timestamp
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
cp "$SESSION_FILE" "$PROJECT_ROOT/ops/sessions/${TIMESTAMP}.json"
