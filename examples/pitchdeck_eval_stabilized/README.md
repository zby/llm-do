# Pitch Deck Evaluation (Stabilized Tools)

This example keeps orchestration in a agent but moves deterministic steps
into Python tools (file discovery + slug generation).

## Path Resolution

`list_pitchdecks()` resolves paths relative to the example directory (project
root), so you can run the manifest from any working directory. Output files
are written to `evaluations/` under the example directory.
