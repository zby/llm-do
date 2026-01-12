# Live Tests: Non-Entry Worker Handoff

## Idea
Create a test harness that can start an entry-only run, then hand off to a live server/runtime to execute a specific non-entry worker directly, enabling clean live tests without internal registry access.

## Why
The current live tests for non-entry workers rely on helper glue to wrap a worker in a synthetic entry. A server-backed handoff would exercise the real runtime path while keeping build_entry the only public builder.

## Rough Scope
- Design a minimal test server/runner contract for targeting a specific worker.
- Implement a handoff flow for live tests (test server -> live server/runtime).
- Update live tests to use the handoff path for non-entry workers.
- Add docs or notes on the handoff testing pattern.

## Why Not Now
Requires runtime/test harness design and likely new infrastructure; not needed to unblock current work.

## Trigger to Activate
Live tests need to validate non-entry workers without synthetic entry helpers, or we introduce a server layer that can direct execution to a specific worker.
