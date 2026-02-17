#!/usr/bin/env bash
# Session orientation hook — fires on SessionStart
# Reads self/ and ops/ to provide continuity across sessions

set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# Session ID from environment or timestamp
SESSION_ID="${CLAUDE_CONVERSATION_ID:-$(date +%Y%m%d-%H%M%S)}"
SESSION_FILE="$PROJECT_ROOT/ops/sessions/current.json"

# Create/update session tracking
mkdir -p "$PROJECT_ROOT/ops/sessions"
cat > "$SESSION_FILE" <<EOF
{
  "session_id": "$SESSION_ID",
  "start_time": "$(date -Iseconds)",
  "notes_created": [],
  "notes_modified": [],
  "discoveries": [],
  "last_activity": "$(date -Iseconds)"
}
EOF

# Collect orientation context
echo "Session started: $SESSION_ID"

# Check for overdue reminders
if [ -f "$PROJECT_ROOT/ops/reminders.md" ]; then
  OVERDUE=$(grep -c '^\- \[ \]' "$PROJECT_ROOT/ops/reminders.md" 2>/dev/null || echo "0")
  if [ "$OVERDUE" -gt 0 ]; then
    echo "Reminders: $OVERDUE pending items in ops/reminders.md"
  fi
fi

# Check inbox pressure
if [ -d "$PROJECT_ROOT/inbox" ]; then
  INBOX_COUNT=$(find "$PROJECT_ROOT/inbox" -name '*.md' -type f 2>/dev/null | wc -l)
  if [ "$INBOX_COUNT" -gt 0 ]; then
    echo "Inbox: $INBOX_COUNT items waiting"
  fi
fi

# Check pending observations
if [ -d "$PROJECT_ROOT/ops/observations" ]; then
  OBS_COUNT=$(find "$PROJECT_ROOT/ops/observations" -name '*.md' -type f 2>/dev/null | wc -l)
  if [ "$OBS_COUNT" -ge 10 ]; then
    echo "Observations: $OBS_COUNT pending (threshold: 10 — consider /arscontexta:rethink)"
  fi
fi

# Check pending tensions
if [ -d "$PROJECT_ROOT/ops/tensions" ]; then
  TENS_COUNT=$(find "$PROJECT_ROOT/ops/tensions" -name '*.md' -type f 2>/dev/null | wc -l)
  if [ "$TENS_COUNT" -ge 5 ]; then
    echo "Tensions: $TENS_COUNT pending (threshold: 5 — consider /arscontexta:rethink)"
  fi
fi
