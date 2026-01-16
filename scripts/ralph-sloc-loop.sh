#!/bin/bash
# Ralph Wiggum Loop for SLOC Reduction
#
# Based on: https://www.aihero.dev/tips-for-ai-coding-with-ralph-wiggum
#
# Usage: ./scripts/ralph-sloc-loop.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
source "$SCRIPT_DIR/ralph-config.sh"

CHECK_SCRIPT="$SCRIPT_DIR/ralph-sloc-check.sh"
PROMPT_FILE="$SCRIPT_DIR/ralph-sloc-prompt.md"
ATTEMPTS_LOG="$PROJECT_DIR/ralph-logs/attempts.md"

cd "$PROJECT_DIR"

# Ensure attempts log exists
mkdir -p "$(dirname "$ATTEMPTS_LOG")"
if [ ! -f "$ATTEMPTS_LOG" ]; then
    cat > "$ATTEMPTS_LOG" << 'EOF'
# SLOC Reduction Attempts Log

This log tracks what has been tried, what worked, and what failed.
Read this before starting a new attempt to avoid repeating mistakes.

---

<!-- Append new attempts below this line -->
EOF
fi

echo "=== Ralph SLOC Reduction Loop ==="
echo "Check script: $CHECK_SCRIPT"
echo "Attempts log: $ATTEMPTS_LOG"
echo "Current SLOC: $(sloccount $LLM_DO_DIR 2>/dev/null | grep -oP 'SLOC\s*=\s*\K[\d,]+')"
echo "Target: < $TARGET_SLOC"
echo ""
echo "Instructions:"
echo "1. Claude Code will start interactively"
echo "2. It will receive the SLOC reduction task"
echo "3. After it finishes, run: ./scripts/ralph-sloc-check.sh"
echo "4. If exit code is 2, tell Claude to continue reducing"
echo ""
echo "Starting Claude Code..."
echo ""

# Start Claude interactively with the prompt file as initial context
claude --dangerously-skip-permissions "$(cat "$PROMPT_FILE")"
