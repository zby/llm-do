# Single-File Workers

**Last Updated**: 2025-12-03
**Status**: Implemented with intentional limitations

## Summary

Workers support two forms:
- **Single-file**: `workers/name.worker` - portable, shareable, no dependencies
- **Directory**: `workers/name/worker.worker` - full power with custom tools and templates

The limitations of single-file workers are intentional - they enable truly portable LLM executables.

## Future Work

### Shebang Support

For true executable feel:
```
#!/usr/bin/env llm-do
---
name: git-helper
---
You help with git operations...
```

Then: `chmod +x git-helper.worker && ./git-helper.worker "prompt"`

**Implementation**: ~50 LOC in CLI to accept file path as first argument.

### LLM_DO_PATH

Environment variable for additional worker search directories (like `PATH`).

### Adjacent File Conventions

Optional patterns for single-file workers that need resources:
```
my_worker.worker
my_worker.tools.py    # Custom tools
my_worker/            # Resources directory
```

Would require changes to `registry.py`.
