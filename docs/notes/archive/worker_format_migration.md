# Worker Format Migration: YAML + Prompts → .worker Files

**Date:** 2025-11-26
**Status:** ✅ Complete

## Summary

Migrated llm-do from separate YAML + prompts files to a unified `.worker` format using front matter (YAML metadata + body content). This simplifies worker definitions by embedding instructions directly in worker files.

## Changes Made

### 1. File Format

**Before:**
```
workers/
  greeter.yaml              # Worker definition
prompts/
  greeter.txt               # Prompt instructions (separate file)
```

**After:**
```
workers/
  greeter.worker            # Unified format with front matter
```

**Format structure:**
```yaml
---
name: greeter
description: A friendly assistant
model: anthropic:claude-sonnet-4
---

You are a friendly and helpful assistant.

When the user provides a message:
1. Greet them warmly
2. Respond thoughtfully to their message
3. Be concise but friendly
```

### 2. Dependencies Added

- **python-frontmatter** (`>=1.0.0`) - For parsing YAML front matter

### 3. Code Changes

#### Registry (llm_do/registry.py)
- Changed extension from `.yaml` to `.worker`
- Integrated Jinja2 template rendering (moved from `prompts.py`)
- Front matter becomes WorkerDefinition fields
- Body becomes `instructions`
- Updated search paths:
  - `workers/{name}.worker`
  - `workers/{name}/worker.worker`
  - `{generated_dir}/{name}/worker.worker`

#### Runtime (llm_do/runtime.py)
- Updated `create_worker()` to save as `.worker` format
- Changed generated worker path from `worker.yaml` to `worker.worker`

#### Removed
- **llm_do/prompts.py** - Functionality moved to registry.py
- **tests/test_prompts.py** - No longer needed
- **prompts/** directories - Deleted from all examples

### 4. Jinja2 Template Support

Templates in `.worker` files work with `file()` function:

```yaml
---
name: evaluator
---

Use this procedure:

{{ file('PROCEDURE.md') }}

Evaluate the pitch deck and provide recommendations.
```

**Support files** (like `PROCEDURE.md`, `RUBRIC.md`) are placed in the worker's directory alongside the `.worker` file.

### 5. Examples Migrated

All 17 worker definitions migrated:
- `examples/greeter/workers/greeter.worker`
- `examples/approvals_demo/workers/save_note.worker`
- `examples/pitchdeck_eval/workers/pitch_evaluator.worker`
- `examples/pitchdeck_eval/workers/pitch_orchestrator.worker`
- `examples/whiteboard_planner/workers/whiteboard_planner.worker`
- `examples/whiteboard_planner/workers/whiteboard_orchestrator.worker`
- `examples/calculator/workers/calculator/worker.worker`
- `examples/code_analyzer/workers/code_analyzer/worker.worker`
- `examples/web_research_agent/workers/` (4 workers)
- `llm_do/workers/worker_bootstrapper.worker`
- Generated workers in `examples/*/workers/generated/`

### 6. Tests Updated

Updated all test files to use `.worker` format:
- `tests/test_bootstrapper.py` - Updated generated worker paths
- `tests/test_pydanticai_base.py` - Updated worker creation tests
- `tests/test_custom_tools.py` - Updated test worker creation
- `tests/test_examples.py` - Updated comments

**Test results:** ✅ All 177 tests passing

## Benefits

1. **Simpler structure** - One file per worker instead of two
2. **Better organization** - Instructions live with their configuration
3. **Easier to read** - No need to jump between files
4. **Preserves Jinja2** - Templates still work with `file()` and `{% include %}`
5. **Clearer ownership** - Each worker is self-contained

## Migration Guide

### For Existing Workers

If you have custom workers in the old format:

1. **Combine files manually:**
   ```bash
   # Old structure:
   #   workers/my_worker.yaml
   #   prompts/my_worker.txt

   # New structure:
   #   workers/my_worker.worker
   ```

2. **New format:**
   ```yaml
   ---
   # (Copy all fields from my_worker.yaml here)
   name: my_worker
   description: My custom worker
   ---

   (Copy contents of prompts/my_worker.txt here)
   ```

3. **For Jinja2 templates:**
   - Move support files (like `.md` includes) to the worker's directory
   - Keep using `{{ file('filename.md') }}` syntax
   - Syntax detection is automatic

### For Generated Workers

Generated workers now use `.worker` format automatically. No changes needed to worker creation code.

## Technical Details

### Front Matter Parsing

```python
import frontmatter

content = path.read_text(encoding="utf-8")
post = frontmatter.loads(content)

data = dict(post.metadata)  # YAML front matter
if post.content.strip():
    data["instructions"] = post.content  # Body after ---
```

### Jinja2 Detection

Templates are detected and rendered automatically:
- Checks for `{{`, `{%`, or `{#` in body
- Uses worker's directory as template root
- Provides `file()` function for includes

### Directory Structure

**Simple workers:**
```
workers/
  greeter.worker
```

**Directory-based workers** (with custom tools or templates):
```
workers/
  calculator/
    worker.worker
    tools.py
```

**Generated workers:**
```
/tmp/llm-do/generated/
  my_generated_worker/
    worker.worker
```

## Backwards Compatibility

**NONE.** This is a breaking change:
- Old `.yaml` + `prompts/` format is no longer supported
- All workers must use `.worker` format
- Migration script was used once and then deleted

## Files Changed

- ✏️ `llm_do/registry.py` - Major rewrite for .worker format
- ✏️ `llm_do/runtime.py` - Updated create_worker() function
- ✏️ `pyproject.toml` - Added python-frontmatter dependency
- ❌ `llm_do/prompts.py` - Removed (functionality moved to registry)
- ❌ `tests/test_prompts.py` - Removed
- ✏️ All example workers - Migrated to .worker format
- ✏️ All test files - Updated references
- ❌ All `prompts/` directories - Removed

## Next Steps

None - migration is complete and all tests are passing.
