#!/usr/bin/env bash
# orphan-notes.sh — Find notes with no incoming wiki links (nothing references them)
#
# A note is an "orphan" if no other markdown file in the workspace contains
# a [[title]] wiki link pointing to it. Orphans are invisible to future agents
# browsing the knowledge graph.
#
# Usage: Run from project root (/home/zby/llm/llm-do)
#   ./ops/queries/orphan-notes.sh

set -euo pipefail

NOTES_DIR="docs/notes"

if [[ ! -d "$NOTES_DIR" ]]; then
  echo "Error: $NOTES_DIR not found. Run from the project root." >&2
  exit 1
fi

orphan_count=0
total_count=0

while IFS= read -r filepath; do
  # Extract the title (filename without .md extension)
  title="$(basename "$filepath" .md)"

  # Skip generic files that aren't real notes
  [[ "$title" == "README" || "$title" == "index" ]] && continue

  total_count=$((total_count + 1))

  # Search all markdown files for a wiki link to this title
  # Exclude the note itself from the search
  if ! rg -q --glob '*.md' "\[\[$title\]\]" "$NOTES_DIR" --glob "!$(basename "$filepath")" 2>/dev/null; then
    # Also check docs/adr/, tasks/, self/, ops/ for references
    found=false
    for search_dir in docs/adr tasks self ops; do
      if [[ -d "$search_dir" ]] && rg -q --glob '*.md' "\[\[$title\]\]" "$search_dir" 2>/dev/null; then
        found=true
        break
      fi
    done

    if [[ "$found" == false ]]; then
      echo "  $filepath"
      orphan_count=$((orphan_count + 1))
    fi
  fi
done < <(find "$NOTES_DIR" -name '*.md' -type f | sort)

echo ""
if [[ $orphan_count -eq 0 ]]; then
  echo "No orphan notes found. ($total_count notes checked)"
else
  echo "$orphan_count orphan note(s) found out of $total_count checked."
  echo "Tip: Add [[wiki links]] to these notes from related notes or indexes."
fi
