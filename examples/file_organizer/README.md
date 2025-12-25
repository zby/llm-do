# File Organizer Example

Demonstrates the **hardening pattern** from [concept.md](../../docs/concept.md): the LLM handles semantic decisions while deterministic Python handles the mechanical parts.

## What It Does

Renames messy filenames to clean, consistent formats:
- `Meeting Notes (2).docx` → `meeting-notes.docx`
- `FINAL_Report_v3.pdf` → `report.pdf`
- `John's Birthday Photo!!.jpg` → `johns-birthday-photo.jpg`

**Simplification**: This organizer only sees filenames, not file contents. It makes decisions purely based on the name. A real organizer might inspect contents to categorize files—that would be another worker call.

## The Hardening Pattern

| Component | Role |
|-----------|------|
| **LLM** | Semantic decisions: "remove 'FINAL' and 'v3'", "this is a date, keep it" |
| **Python** (`sanitize_filename`) | Mechanical cleanup: lowercase, hyphens, safe characters |
| **Approval** | The `mv` command requires operator approval |

## Usage

```bash
cd examples/file_organizer
./reset.sh                                            # Create sample files
llm-do main.worker tools.py "Organize the files"     # Run organizer
./reset.sh                                            # Reset for next demo
```

## Files

- `main.worker` — Worker prompt and tool configuration
- `tools.py` — `sanitize_filename()` function (the hardened part)
- `reset.sh` — Recreates sample files for repeatable demos
- `messy_files/` — Working directory (gitignored)
