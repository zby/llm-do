# Hide EntryRegistry Behind build_entry

## Context
We currently expose `EntryRegistry` and `build_entry_registry` as first-class
API concepts, while `Runtime.run_invocable()` expects an `Entry` object that
callers often obtain via a registry lookup. In practice, most usage is a
single entry point ("main") and callers rarely need to reason about a symbol
table. The proposal is to keep the registry as an internal linking detail,
introduce a `build_entry(...) -> Entry` API, and route execution through
`Runtime.run_invocable()` everywhere.

This note explores the architectural impact, trade-offs, and potential API
shape for a "hidden registry" model that simplifies the public surface without
discarding the two-pass linker that resolves toolset references.

## Findings
### What the registry does today (and why it still matters)
`build_entry_registry()` is not just entry lookup. It performs the link step:
- Load toolsets, workers, and `@entry` functions from Python files.
- Load worker file definitions and create stubs (pass 1).
- Resolve toolset references (names -> instances), including worker toolsets.
- Resolve schema references and apply entry overrides (model, `--set`).
- Produce a single namespace so name-based toolset resolution is consistent.

Even with a single entry, the link step is still required because worker YAML
references toolsets by name. So "removing the registry" in practice means
hiding the symbol table, not deleting the linker.

### Proposed public API
Introduce a simple builder that returns a single resolved entry:

```
entry = build_entry(
    worker_files,
    python_files,
    entry_model_override=...,
    set_overrides=...,
)
```

Then run via:

```
result, ctx = await runtime.run_invocable(entry, input_data)
```

Key points:
- `build_entry()` can call the existing linker internally (current
  `build_entry_registry()`), then return the single resolved entry.
- `EntryRegistry` becomes an internal type (renamed `_EntryRegistry` or moved
  to an internal module).
- `Runtime.run_invocable()` is the standard execution path; entry-name helpers
  are removed in favor of passing an `Entry`.

### Single-entry selection and conflicts
This model assumes the build unit resolves to exactly one entry candidate.
We do not need multiple `@entry` functions; if more than one is present in the
selected Python files, treat it as a hard error.

Candidate selection rules (per file set):
- Discover `@entry` functions; if count > 1, error and list candidates.
- Discover worker entry candidates (explicit marker or convention).
- If both an `@entry` function and an entry worker exist, error.
- If none exist, error ("no entry found").
- If exactly one candidate exists, return it.

### Interface boundaries and naming
If the registry is hidden, the public interface needs clear verbs:
- `build_entry(...)` = link + select.
- `Runtime.run_invocable(...)` = execute.
- For CLI/manifest, a `build_entry_from_manifest(...)` helper may be clearer
  than pushing manifest logic into `build_entry()`.

The emphasis shifts from "registry + entry name" to "entry object", which fits
the mental model of "compiled unit" rather than "symbol table + lookup".

### CLI and manifest implications
Single-entry selection means the manifest/CLI no longer needs `entry.name`.
The build step derives the entry from the file set itself.

Two practical ways to pick the entry worker:
1. **Explicit marker** in worker frontmatter (e.g., `entry: true`).
2. **Convention** (e.g., `main.worker` or worker name `main`).

Either way, the registry is still used internally to resolve toolsets; the
selection logic just chooses which entry candidate to return.

### Impact on tests, docs, and internal call sites
- Tests that construct `EntryRegistry` directly would switch to
  `build_entry(...)` + `run_invocable(...)` or use an internal linker helper.
- `docs/architecture.md` and `docs/reference.md` need to describe linking as an
  internal step and present `build_entry` as the front door.
- Internal runtime calls should consistently use `run_invocable()` to avoid the
  entry-name indirection.

### Benefits
- **Smaller public surface**: one builder, one run method.
- **Clearer mental model**: "link into an entry, then run it".
- **Less incidental complexity**: no registry objects to pass around.
- **More consistent with "single entry" usage** without forbidding multiple
  entries.

### Costs and risks
- **Code removal is modest**: the linker still exists; only wrapper types and
  exports shrink.
- **Entry switching is less direct**: choosing a different entry means changing
  the file set or the entry marker, not just a manifest flag.
- **Loss of introspection**: registry currently provides `names()` for error
  messages and diagnostics; `build_entry()` must preserve good error reporting.
- **Toolset resolution still global**: to resolve `toolsets: ["foo"]`, the
  builder must load the entire toolset namespace, so the hidden registry is
  still doing the heavy lifting.

### Variants worth considering
1. **Thin wrapper only**: add `build_entry()`, keep `EntryRegistry` internal but
   retain `build_entry_registry()` for tests and internal use.
2. **Aggressive hide**: move registry/linker code into a private module,
   remove exports, and update all docs/tests to avoid registry references.
3. **Explicit marker only**: require `entry: true` in worker frontmatter (or
   a `@entry(primary=True)` decorator) and drop convention lookup entirely.
4. **Convention only**: avoid new schema fields, but enforce uniqueness and
   consistency (e.g., `main.worker` must declare `name: main`).
5. **Entry bundle**: return `(entry, metadata)` where metadata includes
   `available_entries` and `toolsets` for better errors without exposing a full
   registry type.

### Performance and reuse
`build_entry()` returns an `Entry` instance that can be reused across runs, so
linking cost can still be paid once per process. The main concern is multi-entry
execution within the same process; a hidden registry could push that into an
internal or advanced API.

## Open Questions
- Which entry selection mechanism should we standardize on: explicit marker,
  naming convention, or a hybrid that prefers markers?
- Should `build_entry()` accept a manifest directly, or should the manifest
  helper live in the CLI layer?
- If we hide `EntryRegistry`, how do we preserve good error messages (listing
  available entries/toolsets) without re-exposing the registry type?
- Should Python `Worker` instances be entry candidates by default, or only when
  explicitly marked?

## Conclusion
Implemented explicit entry markers with single-entry selection, added
`build_entry(...)` as the public builder, and kept `build_entry_registry()` as
an internal linker (no longer re-exported from `llm_do.runtime`). CLI/manifest
now derive the entry from the file set, and docs/tests were updated to use the
single-entry flow.
