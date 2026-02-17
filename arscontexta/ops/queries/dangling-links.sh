#!/usr/bin/env bash
# dangling-links.sh — Find wiki links that point to non-existent files
#
# A "dangling link" is a [[title]] reference where no file named title.md
# exists anywhere in the workspace. Dangling links break navigation and
# should be resolved by creating the target note or fixing the link.
#
# Usage: Run from project root (/home/zby/llm/llm-do)
#   ./ops/queries/dangling-links.sh

set -euo pipefail

SEARCH_DIRS=("docs/notes" "docs/adr" "tasks" "self" "ops")

# Collect all wiki link targets from all workspace markdown files
dangling_count=0
declare -A seen_targets

for search_dir in "${SEARCH_DIRS[@]}"; do
  [[ -d "$search_dir" ]] || continue

  while IFS= read -r line; do
    # Each line is: filepath:match
    filepath="${line%%:*}"
    target="${line#*:}"

    # Skip single-character links like [[a]], [[s]], [[d]], [[q]] (UI keybindings)
    [[ ${#target} -le 1 ]] && continue

    # Build a lookup key to avoid reporting the same target multiple times
    key="$target"
    if [[ -n "${seen_targets[$key]+x}" ]]; then
      # Already reported or checked this target
      if [[ "${seen_targets[$key]}" == "dangling" ]]; then
        echo "  $filepath -> [[$target]]"
      fi
      continue
    fi

    # Check if target.md exists anywhere in the workspace
    if find docs/notes docs/adr tasks self ops -name "$target.md" -type f 2>/dev/null | grep -q .; then
      seen_targets[$key]="found"
    else
      seen_targets[$key]="dangling"
      echo "  $filepath -> [[$target]]"
      dangling_count=$((dangling_count + 1))
    fi
  done < <(rg -o --no-filename '\[\[([^\]]+)\]\]' -r '$1' --glob '*.md' "$search_dir" 2>/dev/null | sort -u | while read -r target; do
    # Re-search to find which file contains this link
    rg -l --glob '*.md' "\[\[$target\]\]" "$search_dir" 2>/dev/null | while read -r file; do
      echo "$file:$target"
    done
  done)
done

echo ""
if [[ $dangling_count -eq 0 ]]; then
  echo "No dangling links found."
else
  echo "$dangling_count dangling link target(s) found."
  echo "Tip: Create the missing notes or fix the wiki link references."
fi
