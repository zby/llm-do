# File Organizer Example

Demonstrates the **stabilizing pattern**: the LLM makes semantic decisions while deterministic Python handles mechanical cleanup.

## What It Does

Renames messy filenames to clean, consistent formats:
- `Meeting Notes (2).docx` → `meeting-notes.docx`
- `FINAL_Report_v3.pdf` → `report.pdf`
- `John's Birthday Photo!!.jpg` → `johns-birthday-photo.jpg`

**Simplification**: This organizer only sees filenames, not file contents. A real organizer might inspect contents to categorize files.

## The Pattern

| Component | Role | Approval |
|-----------|------|----------|
| **LLM** | Semantic decisions: "this is a Report, not FINAL_Report_v3" | — |
| **`sanitize_filename`** | Mechanical cleanup: lowercase, hyphens, safe chars | Pre-approved (pure function) |
| **`mv`** | Actually rename the file | Requires approval |

The LLM passes human-readable names like "Meeting Notes.docx" to `sanitize_filename`, which returns "meeting-notes.docx". This separation means:
- Consistent formatting (no LLM variability in character handling)
- The semantic decision (what to call it) stays with the LLM
- The mechanical decision (how to format it) is deterministic Python

## Running

```bash
export LLM_DO_MODEL="anthropic:claude-haiku-4-5"
cd examples/file_organizer              # Required: shell commands run from cwd
./reset.sh                              # Create sample files
llm-do project.json                     # Run organizer (uses default prompt)
./reset.sh                              # Reset for next demo
```

Note: This example uses `shell_file_ops` which runs shell commands (`ls`, `mv`) from the
current working directory, so `cd` is required.

## Files

- `project.json` — Manifest defining entry point, files, and approval mode
- `main.agent` — Worker prompt and tool configuration
- `tools.py` — `sanitize_filename()` function (the stabilized part)
- `reset.sh` — Recreates sample files for repeatable demos
- `messy_files/` — Working directory (gitignored)
