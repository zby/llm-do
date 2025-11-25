# Worker Bootstrapping (Experimental)

> **Status**: Experimental. The API and behavior may change.

The `worker_bootstrapper` is a built-in meta-worker that creates other workers on-the-fly based on natural language task descriptions.

**This is YOLO territory.** You're letting an LLM design and create executable artifacts (workers) based on natural language. The bootstrapper makes this manageable with approval gates, but the core idea is inherently adventurous.

## Overview

Instead of manually writing worker definitions, you describe what you want to accomplish and the bootstrapper:

1. Analyzes your input files
2. Designs a specialized worker for the task
3. Creates and saves the worker definition
4. Invokes the worker to process your files
5. Writes results to the output directory

## Quick Start

```bash
# Create a project directory with input/output folders
mkdir my-project && cd my-project
mkdir input output

# Add files to process
cp ~/documents/*.pdf input/

# Run the bootstrapper
llm-do worker_bootstrapper --model anthropic:claude-sonnet-4 \
  "Analyze the PDFs and write summaries to output/"
```

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                  worker_bootstrapper                     │
│                                                          │
│  1. List files in input/                                 │
│  2. Decide what worker is needed                         │
│  3. worker_create("pdf_analyzer", instructions=...)      │
│  4. worker_call("pdf_analyzer", attachments=[...])       │
│  5. write_file("output/result.md", ...)                  │
└─────────────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐   ┌─────────────────┐
│ workers/        │   │ output/         │
│  generated/     │   │  result.md      │
│   pdf_analyzer  │   │                 │
│    .yaml        │   │                 │
└─────────────────┘   └─────────────────┘
```

Created workers are saved to `workers/generated/` and can be reused directly:

```bash
# Reuse the created worker
llm-do pdf_analyzer --attach input/new_file.pdf
```

## Example Session

```bash
$ llm-do worker_bootstrapper --model anthropic:claude-haiku-4-5 \
  "Analyze the pitch decks and write evaluations"

# Bootstrapper:
# 1. Lists input/ → finds acma_pitchdeck.pdf
# 2. Creates pitch_deck_analyzer worker
# 3. Calls worker with PDF attachment
# 4. Writes output/acma_pitchdeck_evaluation.md

# Output:
# ✅ Task Completed
# - Created worker: pitch_deck_analyzer
# - Processed: 1 pitch deck
# - Output: output/acma_pitchdeck_evaluation.md
```

## Directory Structure

The bootstrapper expects this layout:

```
my-project/
├── input/           # Read-only: source files to process
│   ├── doc1.pdf
│   └── doc2.md
├── output/          # Read-write: results written here
└── workers/
    └── generated/   # Auto-created workers saved here
        └── my_analyzer.yaml
```

## Configuration

The bootstrapper has these built-in permissions:

| Capability | Setting |
|------------|---------|
| Read input files | ✅ Auto-approved |
| Write output files | ⚠️ Requires approval |
| Create workers | ⚠️ Requires approval |
| Call any worker | ✅ Auto-approved |

## Supported File Types

**Text files** (can be read directly):
- `.md`, `.txt`, `.yaml`, `.json`, `.py`

**Binary files** (passed as attachments):
- `.pdf` and other binary formats

## Limitations

- **Experimental**: API may change
- **No iteration**: Created workers are not automatically refined based on output quality
- **Manual approval**: Worker creation and file writes require user approval
- **Single session**: Created workers persist, but the bootstrapper doesn't remember previous sessions

## Double YOLO Mode

The bootstrapper is already YOLO (LLM creates workers). Add `--approve-all` for **double YOLO**:

```bash
# Double YOLO: fully autonomous worker creation and execution
llm-do worker_bootstrapper --model anthropic:claude-sonnet-4 --approve-all \
  "Process all documents in input/ and generate reports"
```

No prompts. No confirmations. The LLM:
- Designs workers
- Creates them
- Calls them
- Writes output files

All without asking. **Review `workers/generated/` afterward to see what emerged.**

## Best Practices

1. **Be specific** about the task and expected output format
2. **Use attachments** for PDFs and images rather than trying to read them as text
3. **Check generated workers** in `workers/generated/` and refine them manually if needed
4. **Reuse workers** directly once created instead of re-bootstrapping

## Future Work

See `docs/notes/todos/future_work.md` for planned enhancements including automatic iterative refinement.
