#!/usr/bin/env bash
# sparse-notes.sh — Find notes with fewer than 2 outgoing wiki links
#
# Sparse notes are poorly connected in the knowledge graph. They represent
# knowledge that hasn't been woven into the broader network. Notes should
# ideally link to at least 2 other notes to establish meaningful context.
#
# Usage: Run from project root (/home/zby/llm/llm-do)
#   ./ops/queries/sparse-notes.sh

set -euo pipefail

NOTES_DIR="docs/notes"
MIN_LINKS=2

if [[ ! -d "$NOTES_DIR" ]]; then
  echo "Error: $NOTES_DIR not found. Run from the project root." >&2
  exit 1
fi

sparse_count=0
total_count=0

while IFS= read -r filepath; do
  title="$(basename "$filepath" .md)"

  # Skip generic files
  [[ "$title" == "README" || "$title" == "index" ]] && continue

  total_count=$((total_count + 1))

  # Count unique outgoing wiki links in this file
  link_count=$(rg -o '\[\[([^\]]+)\]\]' -r '$1' "$filepath" 2>/dev/null | sort -u | wc -l)

  if [[ $link_count -lt $MIN_LINKS ]]; then
    echo "  [$link_count links] $filepath"
    sparse_count=$((sparse_count + 1))
  fi
done < <(find "$NOTES_DIR" -name '*.md' -type f | sort)

echo ""
if [[ $sparse_count -eq 0 ]]; then
  echo "All notes have $MIN_LINKS+ outgoing wiki links. ($total_count notes checked)"
else
  echo "$sparse_count sparse note(s) found out of $total_count checked (fewer than $MIN_LINKS outgoing links)."
  echo "Tip: Run /connect on these notes to find relationships in the graph."
fi
