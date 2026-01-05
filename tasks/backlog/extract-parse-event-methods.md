# Extract Methods from parse_event()

## Idea

Refactor `parse_event()` in `llm_do/ui/parser.py` (117 lines) into smaller, focused methods. The function currently has 9 isinstance checks forming a long conditional chain that handles different event types.

## Why

- **Readability**: The function is too long and handles too many concerns
- **Testability**: Individual parsing logic cannot be unit tested in isolation
- **Maintainability**: Adding new event types requires modifying a large function
- **Single Responsibility**: Each event type deserves its own parsing function

## Rough Scope

Extract these methods from `parse_event()`:

1. `_parse_initial_request(payload, worker)` - lines 57-64
2. `_parse_status(payload, worker)` - lines 67-77
3. `_parse_error(payload, worker)` - lines 80-89
4. `_parse_deferred_tool(payload, worker)` - lines 92-98
5. `_parse_pydantic_ai_event(event, worker)` - lines 105-153 (the big isinstance chain for PydanticAI events)

The main `parse_event()` becomes a dispatcher that checks for top-level keys and delegates to the appropriate handler.

## Why Not Now

Currently refactoring other parts of the system. This is a contained change that can wait.

## Trigger to Activate

- When modifying parser.py for other reasons (good time to clean up)
- When adding a new event type (the pain of the current design becomes acute)
- During a dedicated code quality sprint

## References

- **File**: `llm_do/ui/parser.py:36-153`
- **Analysis**: `docs/notes/reviews/fowler.md` (Critical item #1 in UI Code section)
