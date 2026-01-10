# Toolsets as Import Tables (Compiler Analogy)

## Context
This extends the "messages as locals" mental model in `docs/notes/messages-as-locals.md`
to clarify how tool availability works. The goal is to use a compiler analogy to
make the scoping story sharper: toolsets are global, while individual tools are
local to a worker's scope.

## Findings
- Treat the global tool registry as a global symbol table or linker universe.
- Treat each worker's toolset as an import table (a per-worker binding of
  allowed symbols from the global registry).
- Individual tools are like functions/intrinsics that must resolve through the
  worker's import table, not directly from globals.
- Tool calls are effectful intrinsics/syscalls, which makes the capability and
  approval model feel like effect typing.
- This framing aligns with the existing "messages are locals" rule: messages
  are stack locals, runtime config is global, toolsets are scoped imports.

Potential documentation targets that could benefit from this frame:
- `docs/architecture.md` (worker/runtime boundaries, tool resolution)
- `README.md` (high-level model for users)
- `docs/notes/messages-as-locals.md` (add toolset scoping alongside messages)
- `docs/notes/recursive-problem-patterns.md` (tie recursion patterns to scoped imports)

## Open Questions
- Is a worker's toolset immutable after creation (lexical imports), or can it
  be updated dynamically (dynamic linking)?
- Do we allow tool aliasing/shadowing in a toolset, or is it a flat namespace?
- Should the capability/effect story be formalized (e.g., "tool calls are IO")?

## Conclusion
(Add when resolved) Where this framing should be adopted and what terms to use.
