# OAuth Storage Dependency Injection

## Status
completed

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
- Decision: Option A (OAuthStorage wrapper with injectable backend).
- Problem:
  - Module-level `_storage_backend` is global mutable state
  - Callers forced to use `set_oauth_storage()` to swap backends (side effects)
  - Hard to test without mutating global state
  - Violates Dependency Inversion Principle
- Options:
  - A) **Storage class with instance methods**: Create `OAuthStorage` class that takes backend in `__init__`, replace module functions with methods. CLI creates instance.
  - B) **Pass backend to each function**: Add `backend: OAuthStorageBackend = None` param to each function, defaulting to `FileSystemStorage()`.
- Outcome:
  - Implemented `OAuthStorage` and removed global backend/mutators.
  - Updated CLI and OAuth helpers to take explicit storage.

## Tasks
- [x] Decide on approach (A/B/C/D)
- [x] Implement chosen approach
- [x] Update `oauth_cli.py` to use new API
- [x] Update any other callers
- [x] Add/update tests for OAuth storage
- [x] Remove global `_storage_backend` and mutator functions
- [x] Run `uv run pytest`

## Current State
OAuth storage now uses an injectable `OAuthStorage` wrapper. CLI and OAuth helpers accept storage instances. Tests pass (`uv run pytest`).

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
