# Base Path and Working Directory Design

## The Problem

When running scripts or workers from a different directory than where they live,
relative paths break. This is a common problem in multi-component systems where:

- File tools need to read/write relative to a project directory
- Workers receive attachments with relative paths
- Instructions reference local files

## How Other Systems Handle This

### Bash Scripts

Bash scripts typically use `cd` at the start to align the working directory:

```bash
#!/bin/bash
cd "$(dirname "$0")"  # Change to script's directory
# Now all relative paths work
./run.sh
cat input/data.txt
```

Pros:
- Simple, one-liner solution
- All relative paths just work

Cons:
- Global side effect (changes CWD for entire process)
- Can break other code that depends on original CWD
- Not composable (nested scripts may fight over CWD)

### Python Scripts with Global Constant

Python scripts often define a base directory constant:

```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()

# Use BASE_DIR explicitly
config_path = BASE_DIR / "config.yaml"
data_dir = BASE_DIR / "data"
```

Pros:
- Explicit, no global side effects
- Multiple base directories can coexist
- Composable

Cons:
- Must thread the constant through all code that needs it
- Easy to forget and use bare relative paths
- Duplication when multiple components need the same base

## Current llm-do Approach

We added `base_path` configuration to both:

1. **FileSystemToolset** - for file operations (read, write, list)
2. **Worker** - for resolving attachment paths

This requires duplicating the base_path in both places:

```python
HERE = Path(__file__).parent

filesystem = FileSystemToolset(config={"base_path": str(HERE)})

pitch_evaluator = Worker(
    name="pitch_evaluator",
    instructions=load_instructions("pitch_evaluator"),
    toolsets=[],
    base_path=HERE,  # Duplication!
)
```

This is not ideal but workable for now.

## User Stories

### Story 1: Running Examples from Project Root

As a developer, I want to run example scripts from the project root directory
so that I can test them without changing directories.

```bash
# From ~/projects/llm-do
uv run python experiments/inv/v2_direct/run.py
```

The script's instructions say "read files from input/" but CWD is ~/projects/llm-do,
not experiments/inv/v2_direct/. Without base_path, file operations fail.

### Story 2: IDE Integration

As a developer using VS Code, I want to run/debug worker scripts using the IDE's
run button. The IDE runs from the workspace root, not the script's directory.

Without base_path configuration, I'd have to manually cd or configure launch.json
for every script.

### Story 3: Nested Worker Calls with Attachments

As a developer, I have a main worker that finds PDFs and delegates to an evaluator
worker with attachments:

```
main worker:
  1. list_files("input/*.pdf")  -> ["input/doc.pdf"]
  2. call pitch_evaluator with attachment "input/doc.pdf"

pitch_evaluator worker:
  1. Receives attachment "input/doc.pdf"
  2. Needs to load the file
```

The FileSystemToolset (used by main) and Worker (pitch_evaluator receiving
attachments) need the same base_path to resolve "input/doc.pdf" correctly.

### Story 4: Reusable Worker Libraries

As a developer, I want to package workers as reusable libraries that can be
invoked from any directory.

```python
# In my-workers/evaluators.py
from pathlib import Path
HERE = Path(__file__).parent

def get_evaluator():
    return Worker(
        name="evaluator",
        instructions=(HERE / "prompts/evaluator.md").read_text(),
        base_path=HERE,  # Workers know their own base
    )
```

The worker should work regardless of what directory the calling code runs from.

## Future Improvements

A cleaner design might:

1. **Unify at runtime level**: Have a single `RuntimeConfig.base_path` that all
   components inherit, rather than configuring each separately.

2. **Implicit from worker file**: When loading a worker from a .md or .py file,
   automatically set base_path to that file's directory.

3. **Path resolution protocol**: Define a `PathResolver` protocol that toolsets
   and workers use, injected via the runtime context.

4. **Relative path wrapper**: A `RelativePath` type that carries its base,
   resolved lazily when accessed.

For now, explicit `base_path` on each component works, with the understanding
that they must be kept in sync manually.
