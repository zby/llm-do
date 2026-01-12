# Review: Test Suite Cleanup

Periodic review of tests to keep them aligned with current llm-do behavior and public contracts.

## Scope

- `tests/` - core unit/behavior tests
- `tests/runtime/` - runtime behavior and API contracts
- `tests/ui/` - UI controllers
- `tests/live/` - example/integration tests
- `tests/README.md` - testing patterns and fixtures

## Review Prompt

Goal: keep tests aligned with current intended behavior and public contracts, not historical internals. Do not change library behavior unless you find a clear bug.

Constraints:
- Keep the suite green; run `uv run pytest` after each patch or file set.
- Prefer rewriting tests to match current behavior; delete only if obsolete or pure duplication.
- Avoid assertions on private internals or exact error strings unless part of a documented contract.
- If uncertain, mark "NEEDS HUMAN REVIEW" in the report.

Process:
1) Inventory: list all test modules and classify each file as:
   A) public API/contract
   B) behavior/regression (user-visible)
   C) integration (multiple components/examples)
   D) implementation-coupled unit tests
   E) obsolete/legacy surface
   For each file, add 1-2 sentences on the contract it protects.
2) Obsolescence scan: find tests referencing removed APIs, deprecated flags, brittle error strings, or internal call order. Capture intent and whether it is still relevant.
3) Action plan (before edits): group into KEEP/REWRITE/DELETE/CONSOLIDATE with justification and risk.
   - Record the inventory + plan in `docs/notes/reviews/review-tests.md` before any code changes.
4) Apply changes iteratively: small patches per file/theme; rerun tests each time; keep assertions on stable outcomes (public outputs, exception types, state transitions). Follow `tests/README.md` patterns (TestModel/custom runner; avoid real models unless required).
5) Deliverables:
   - Report at `docs/notes/reviews/review-tests.md`:
     - Summary counts (kept/rewritten/deleted)
     - Contracts covered
     - Gaps/follow-ups
     - NEEDS HUMAN REVIEW items
   - Test changes with all tests passing.

Output format in chat:
- First: inventory + action plan (no code changes yet).
- Then: apply changes and show diffs file-by-file.
- End: paste final report content.

## Checklist

- [ ] Inventory + classification complete
- [ ] Obsolescence scan notes captured
- [ ] Action plan agreed
- [ ] Iterative patches with `uv run pytest`
- [ ] Report written to `docs/notes/reviews/review-tests.md`

## Output

Record findings in `docs/notes/reviews/review-tests.md`. Start with inventory + action plan and note that no edits have been made yet if you stop early.

## Last Run

2026-01 (inventory + action plan recorded; no code changes yet)
