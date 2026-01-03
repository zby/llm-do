# Library System Implementation

## Idea
Implement the library system described in docs/notes/library-system-spec.md to allow reusable workers, tools, and templates across projects.

## Why
Reusable libraries reduce copy/paste and make shared worker ecosystems viable.

## Rough Scope
- Add library types and resolution helpers.
- Update registry/template/tool discovery to handle lib: references.
- Add CLI commands for install/list/info/remove.
- Tests, docs, and a sample library.

## Why Not Now
Spec is still draft and open questions remain on tool aggregation and dependency behavior.

## Trigger to Activate
Repeated need to share workers across projects or a concrete request to add library support.
