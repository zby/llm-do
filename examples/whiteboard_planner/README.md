# Whiteboard Planner

Converts whiteboard photos into structured project plans using vision capabilities.

## Running

```bash
export LLM_DO_MODEL="anthropic:claude-haiku-4-5"
llm-do examples/whiteboard_planner
```

Place image files (`.jpg`, `.jpeg`, `.png`) in `examples/whiteboard_planner/input/` before running. Plans are written to `plans/`.

## What It Does

1. **Orchestrator** (`main.agent`) lists images in the input directory
2. For each image, calls the **planner** (`whiteboard_planner.agent`)
3. Planner uses vision to interpret the whiteboard and generates a structured plan
4. Orchestrator writes markdown plans to the plans directory

## Output Format

Each plan includes:
- High-level summary
- Epics/workstreams with prioritized tasks (P0/P1/P2)
- Timeline breakdown
- Open questions and risks

## Project Structure

```
whiteboard_planner/
├── main.agent              # Orchestrator
├── whiteboard_planner.agent # Vision-based planner
├── project.json
├── input/                  # Place images here
└── plans/                  # Markdown plans written here
```

## Key Concepts

- **Vision capabilities**: Planner reads images natively via attachments
- **compatible_models**: Planner requires a vision-capable model
- **Structured extraction**: Converts messy whiteboards into organized plans
