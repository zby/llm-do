# OAuth Storage Dependency Injection

## Status
ready for implementation

## Prerequisites
- [x] none

## Goal
Replace module-level global `_storage_backend` with dependency injection so callers can provide storage backends explicitly, improving testability and SOLID alignment.

## Context
- Relevant files/symbols:
  - `llm_do/oauth/storage.py:112`: `_storage_backend: OAuthStorageBackend = FileSystemStorage()`
  - `llm_do/oauth/storage.py:115-124`: `set_oauth_storage()`, `reset_oauth_storage()` — global state mutators
  - `llm_do/oauth/storage.py:132-163`: module-level functions that use `_storage_backend`
  - `llm_do/oauth_cli.py`: CLI that uses these functions
- Related tasks/notes/docs:
  - `docs/notes/reviews/review-solid.md` (Config/auth finding)
- How to verify:
  - `uv run pytest`
  - OAuth CLI still works: `llm-do-oauth login`, `llm-do-oauth status`

## Decision Record
- Decision: TBD — choose between options below
- Problem:
  - Module-level `_storage_backend` is global mutable state
  - Callers forced to use `set_oauth_storage()` to swap backends (side effects)
  - Hard to test without mutating global state
  - Violates Dependency Inversion Principle
- Options:
  - A) **Storage class with instance methods**: Create `OAuthStorage` class that takes backend in `__init__`, replace module functions with methods. CLI creates instance.
  - B) **Pass backend to each function**: Add `backend: OAuthStorageBackend = None` param to each function, defaulting to `FileSystemStorage()`.
  - C) **Context manager**: `with oauth_storage(backend): ...` temporarily sets backend for a scope.
  - D) **Keep global but add explicit param**: Functions accept optional `backend` param, fall back to global if not provided.
- Recommendation: **Option A** — cleaner API, explicit dependencies, easy to test

## Tasks
- [ ] Decide on approach (A/B/C/D)
- [ ] Implement chosen approach
- [ ] Update `oauth_cli.py` to use new API
- [ ] Update any other callers
- [ ] Add/update tests for OAuth storage
- [ ] Remove global `_storage_backend` and mutator functions
- [ ] Run `uv run pytest`

## Current State
Task created from SOLID review. Ready for decision and implementation.

## Notes
- Current code already has `OAuthStorageBackend` protocol — good foundation
- `FileSystemStorage` and `InMemoryStorage` implementations exist
- Global state makes testing awkward (need to remember to reset)
- Option A example:
  ```python
  class OAuthStorage:
      def __init__(self, backend: OAuthStorageBackend = None):
          self._backend = backend or FileSystemStorage()

      def load(self) -> Dict[str, OAuthCredentials]: ...
      def save_credentials(self, provider: str, creds: OAuthCredentials): ...
      # etc.

  # CLI usage:
  storage = OAuthStorage()  # uses default FileSystemStorage

  # Test usage:
  storage = OAuthStorage(InMemoryStorage())
  ```
