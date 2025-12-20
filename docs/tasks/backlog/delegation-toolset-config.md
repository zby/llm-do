# Delegation Toolset-Level Config

## Current Implementation

Both `worker_create` and `worker_call` now support directory configuration:

```yaml
toolsets:
  delegation:
    worker_call:
      workers_dir: ./workers/generated  # Where to look for workers
    worker_create:
      output_dir: ./workers/generated   # Where to save new workers
    summarizer: {}  # This is a worker tool
```

**Important**: Both must be set to the same directory for created workers to be callable.

## Future Improvement: Shared Config

Consider adding a shared config key to avoid duplication:

```yaml
toolsets:
  delegation:
    _config:
      generated_dir: ./workers/generated  # Shared by both tools
    worker_call: {}
    worker_create: {}
    summarizer: {}
```

This pattern already exists for `_approval_config` in custom toolsets.

### Implementation Notes

1. Add `_config` to `_RESERVED_TOOLS` set in delegation_toolset.py
2. Parse `_config.generated_dir` as fallback when tool-specific config is not set
3. Tool-specific config (`output_dir`, `workers_dir`) would override the shared config

## Alternative: Registry-Level Config

Could also be set at registry/CLI level:
```bash
llm-do --generated-dir ./workers/generated "task..."
```

This might be simpler but less flexible for per-worker customization.
