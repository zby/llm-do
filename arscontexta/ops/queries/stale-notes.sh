#!/usr/bin/env bash
# stale-notes.sh — Find notes not modified in 30+ days that have sparse connections
#
# Stale notes are old AND poorly connected — they risk becoming dead weight
# in the knowledge graph. A well-connected old note is fine (it's established
# knowledge). A sparsely-connected old note likely needs revisiting.
#
# Usage: Run from project root (/home/zby/llm/llm-do)
#   ./ops/queries/stale-notes.sh [days]
#
# Optional argument: number of days (default: 30)

set -euo pipefail

NOTES_DIR="docs/notes"
STALE_DAYS="${1:-30}"
MAX_LINKS=2  # "sparse" threshold — fewer than this many outgoing links

if [[ ! -d "$NOTES_DIR" ]]; then
  echo "Error: $NOTES_DIR not found. Run from the project root." >&2
  exit 1
fi

cutoff_epoch=$(date -d "$STALE_DAYS days ago" +%s 2>/dev/null || date -v-"${STALE_DAYS}"d +%s 2>/dev/null)
stale_count=0
total_count=0

while IFS= read -r filepath; do
  title="$(basename "$filepath" .md)"

  # Skip generic files
  [[ "$title" == "README" || "$title" == "index" ]] && continue

  total_count=$((total_count + 1))

  # Get file modification time
  mod_epoch=$(stat -c %Y "$filepath" 2>/dev/null || stat -f %m "$filepath" 2>/dev/null)
  if [[ -z "$mod_epoch" ]]; then
    continue
  fi

  # Check if the file is older than the cutoff
  if [[ $mod_epoch -lt $cutoff_epoch ]]; then
    # Count outgoing wiki links
    link_count=$(rg -o '\[\[([^\]]+)\]\]' -r '$1' "$filepath" 2>/dev/null | sort -u | wc -l)

    # Count incoming wiki links (backlinks from other files)
    backlink_count=$(rg -l --glob '*.md' "\[\[$title\]\]" "$NOTES_DIR" 2>/dev/null | grep -v "$filepath" | wc -l)

    total_links=$((link_count + backlink_count))

    if [[ $total_links -lt $MAX_LINKS ]]; then
      # Calculate days since last modification
      days_old=$(( ($(date +%s) - mod_epoch) / 86400 ))
      echo "  [${days_old}d old, ${link_count} out + ${backlink_count} in links] $filepath"
      stale_count=$((stale_count + 1))
    fi
  fi
done < <(find "$NOTES_DIR" -name '*.md' -type f | sort)

echo ""
if [[ $stale_count -eq 0 ]]; then
  echo "No stale notes found. ($total_count notes checked, threshold: ${STALE_DAYS} days + <${MAX_LINKS} total links)"
else
  echo "$stale_count stale note(s) found out of $total_count checked."
  echo "Criteria: not modified in ${STALE_DAYS}+ days AND fewer than ${MAX_LINKS} total connections."
  echo "Tip: Run /revisit on these notes to update them with current context."
fi
