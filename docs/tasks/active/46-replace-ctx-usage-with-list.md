# Replace ctx.usage dict with list of RunUsage

## Prerequisites
- None

## Goal
Replace `ctx.usage` (currently `dict[str, RunUsage]`) with a simple `list[RunUsage]` to collect usage data from all agent runs. Later work will add summarization per model and cost estimation.

## Tasks
- [ ] Update Context.__init__ signature: change `usage: Optional[dict[str, RunUsage]]` to `usage: Optional[list[RunUsage]]`
- [ ] Update usage initialization from `{}` to `[]`
- [ ] Refactor `_get_usage()` method to create and append new RunUsage instead of dict lookup
- [ ] Update `_make_run_context()` to use the new usage tracking approach
- [ ] Verify child context sharing still works (_child and _clone methods)
- [ ] Add TODO comment about future synchronization for concurrent workers
- [ ] Run tests to ensure no regressions
- [ ] Run linting and formatting checks

## Current State
Analysis complete. Ready to implement changes.

## Analysis

### Current Implementation
Location: `llm_do/ctx_runtime/ctx.py`

```python
# Line 129: __init__ parameter
usage: Optional[dict[str, RunUsage]] = None,

# Line 143: Initialization
self.usage = usage if usage is not None else {}

# Lines 159-164: Get or create usage per model
def _get_usage(self, model: ModelType) -> RunUsage:
    """Get or create RunUsage tracker for a model."""
    key = str(model)
    if key not in self.usage:
        self.usage[key] = RunUsage()
    return self.usage[key]

# Line 173: Used in _make_run_context
usage=self._get_usage(resolved_model),

# Lines 201, 224: Shared across child contexts
usage=self.usage,  # in _child() and _clone()
```

### Changes Required

1. **Type signature change** (line 129, 143):
   - From: `Optional[dict[str, RunUsage]]` with default `{}`
   - To: `Optional[list[RunUsage]]` with default `[]`

2. **Refactor `_get_usage()` method** (lines 159-164):
   - Current: Returns existing or creates new RunUsage keyed by model
   - New approach: Create new RunUsage, append to list, return it
   - Alternative: Remove method entirely and handle inline

3. **Update `_make_run_context()`** (line 173):
   - Must create a new RunUsage instance
   - Append it to the list
   - Pass it to RunContext

4. **No changes needed** for `_child()` and `_clone()`:
   - Already pass `self.usage` reference
   - List will be shared correctly (Python lists are mutable references)

5. **Add synchronization TODO**:
   - Comment noting future need for thread-safe appends
   - Consider `threading.Lock` or `queue.Queue` when implementing concurrent workers

### Design Decisions

**Why list instead of dict?**
- Simpler data structure
- Preserves chronological order of agent runs
- Defers model-based aggregation to future summarization code
- Easier to extend with additional metadata later

**Thread safety consideration:**
```python
# Future TODO when implementing concurrent workers:
# - Wrap list access with threading.Lock
# - Or use queue.Queue for thread-safe appends
# - Or use process-safe alternatives for multiprocessing
```

### Files Affected
- `llm_do/ctx_runtime/ctx.py` - main changes
- No test changes expected (no tests currently verify usage tracking)

### Risk Assessment
**Low risk:**
- Usage tracking is internal implementation detail
- No external API surface changes
- Tests don't currently verify usage behavior
- Child context sharing will work identically with list reference

## Notes
- User explicitly stated this is a first step; summarization/cost estimation comes later
- No need to preserve model-keyed lookup since summarization is future work
- The `_get_usage()` method name might be misleading after changes - consider renaming to `_create_usage()` or removing entirely
