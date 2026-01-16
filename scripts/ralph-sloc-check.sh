#!/bin/bash
# Ralph Wiggum check script for SLOC reduction
# Exit codes:
#   0 = SUCCESS (goal achieved, stop looping)
#   2 = CONTINUE (not done yet, keep looping)
#   1 = ERROR (something broke, stop looping)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/ralph-config.sh"

echo "=== Ralph SLOC Reduction Check ==="
echo ""

# Step 1: Run tests
echo ">>> Running tests..."
if ! uv run pytest -q 2>&1; then
    echo "FAIL: Tests failed"
    exit 1
fi
echo "PASS: Tests"
echo ""

# Step 2: Run linter
echo ">>> Running ruff..."
if ! uv run ruff check . 2>&1; then
    echo "FAIL: Lint errors"
    exit 1
fi
echo "PASS: Lint"
echo ""

# Step 3: Run type checker
echo ">>> Running mypy..."
if ! uv run mypy $LLM_DO_DIR 2>&1; then
    echo "FAIL: Type errors"
    exit 1
fi
echo "PASS: Types"
echo ""

# Step 4: Check SLOC
echo ">>> Checking SLOC..."
SLOC=$(sloccount $LLM_DO_DIR 2>/dev/null | grep "^Total Physical" | grep -oP '\d+,?\d*' | tr -d ',')
echo "Current SLOC: $SLOC (target: < $TARGET_SLOC)"
echo ""

if [ "$SLOC" -lt "$TARGET_SLOC" ]; then
    echo "=== SUCCESS: SLOC target achieved! ==="
    echo "Reduced to $SLOC lines (below $TARGET_SLOC)"
    exit 0
else
    REMAINING=$((SLOC - TARGET_SLOC + 1))
    echo "=== CONTINUE: Need to reduce $REMAINING more lines ==="
    exit 2
fi
