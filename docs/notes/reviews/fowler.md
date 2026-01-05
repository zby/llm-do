# Fowler Refactoring Opportunities

_Generated review of classic refactoring patterns from Martin Fowler's catalog._

---

## UI Code (llm_do/ui/)

### Critical (High impact, Low risk)

#### 1. Extract Method: `parse_event()` in parser.py
- **Location:** `llm_do/ui/parser.py:36-153` (117 lines)
- **Code Smell:** Long function with 9 isinstance checks forming a conditional chain
- **Recommended Refactoring:** Extract into `_parse_initial_request()`, `_parse_status()`, `_parse_error()`, `_parse_deferred_tool()`, `_parse_pydantic_ai_event()`
- **Expected Benefit:** Reduces cognitive load, makes dispatch logic clearer, enables unit testing of individual parsers

#### 2. Dead Code: Unused `signal_done()` method
- **Location:** `llm_do/ui/app.py:372-374`
- **Code Smell:** Method defined but never called anywhere in codebase
- **Recommended Refactoring:** Remove the method
- **Expected Benefit:** Reduces maintenance burden and confusion

#### 3. Dead Code: Unused enum value `ExitDecision.IGNORE`
- **Location:** `llm_do/ui/controllers/exit_confirmation.py:10`
- **Code Smell:** Enum value defined but never referenced
- **Recommended Refactoring:** Remove the unused enum value
- **Expected Benefit:** Cleaner API, less confusion

### Important (Medium impact)

#### 4. Magic Number: Duplicated truncation constant
- **Location:** `llm_do/ui/widgets/messages.py:159-171`
- **Code Smell:** Hardcoded `500` duplicates `ToolResultEvent.MAX_RESULT_DISPLAY`
- **Recommended Refactoring:** Import and use `ToolResultEvent.MAX_RESULT_DISPLAY` instead
- **Expected Benefit:** Single source of truth for truncation limits

#### 5. Extract Method: `_format_approval_request()` in messages.py
- **Location:** `llm_do/ui/widgets/messages.py:225-265` (40 lines)
- **Code Smell:** Long function mixing header formatting, content formatting, and action hints
- **Recommended Refactoring:** Extract `_format_approval_header()` and `_format_approval_actions()`
- **Expected Benefit:** Separates presentation concerns, easier to modify approval UI

#### 6. Introduce Parameter Object: `LlmDoApp.__init__()`
- **Location:** `llm_do/ui/app.py:81-91`
- **Code Smell:** 5 parameters passed together representing app configuration
- **Recommended Refactoring:** Create `AppConfig` dataclass grouping `event_queue`, `approval_response_queue`, `worker_coro`, `run_turn`, `auto_quit`
- **Expected Benefit:** Cleaner constructor, configuration can be passed around as unit

#### 7. Extract Class: `TruncationConfig` utility
- **Location:** `llm_do/ui/events.py` (multiple classes)
- **Code Smell:** Truncation constants and `_truncate()` method duplicated in `ToolCallEvent`, `InitialRequestEvent`, `ToolResultEvent`
- **Recommended Refactoring:** Extract `TruncationConfig` dataclass with `max_length`, `max_lines`, `suffix` and `truncate()` method
- **Expected Benefit:** DRY truncation logic, consistent behavior

#### 8. Empty Exception Handler
- **Location:** `llm_do/ui/app.py:364-365`
- **Code Smell:** Silent `except Exception: pass` swallows all errors during error display
- **Recommended Refactoring:** Log the exception or use a more specific exception type
- **Expected Benefit:** Easier debugging, prevents hidden bugs

### Minor (Low impact, Nice to have)

#### 9. Magic Number: Console width
- **Location:** `llm_do/ui/display.py:58`
- **Code Smell:** Hardcoded `width=120` for Rich Console
- **Recommended Refactoring:** Extract to `DEFAULT_CONSOLE_WIDTH = 120`
- **Expected Benefit:** Documented constant, easy to configure

#### 10. Magic Number: Event poll timeout
- **Location:** `llm_do/ui/app.py:151`
- **Code Smell:** Hardcoded `timeout=0.1` in asyncio.wait_for
- **Recommended Refactoring:** Extract to `EVENT_POLL_TIMEOUT_SECONDS = 0.1`
- **Expected Benefit:** Documented timeout value

#### 11. Magic Number: Turn separator width
- **Location:** `llm_do/ui/widgets/messages.py:370`
- **Code Smell:** Hardcoded `48` for separator width
- **Recommended Refactoring:** Extract to `TURN_SEPARATOR_WIDTH = 48`
- **Expected Benefit:** Consistent styling, easy to adjust

#### 12. Redundant Conditional
- **Location:** `llm_do/ui/app.py:242-246, 292`
- **Code Smell:** `_input_is_active()` checked in both `check_action()` and `action_quit_if_idle()`
- **Recommended Refactoring:** Remove redundant check in `action_quit_if_idle()` since `check_action()` already prevents the action
- **Expected Benefit:** Simpler logic, single point of control

#### 13. Unnecessary Indirection
- **Location:** `llm_do/ui/widgets/messages.py:24-27`
- **Code Smell:** `_tool_call_max_args_display()` wrapper function just returns a constant
- **Recommended Refactoring:** Import `ToolCallEvent.MAX_ARGS_DISPLAY` directly at module level
- **Expected Benefit:** Simpler code, no function call overhead

#### 14. Missing Exports
- **Location:** `llm_do/ui/__init__.py`, `llm_do/ui/widgets/__init__.py`
- **Code Smell:** `UserMessageEvent`, `UserMessage`, `TurnSeparator`, `ErrorMessage`, `ApprovalPanel` defined but not exported
- **Recommended Refactoring:** Add to `__all__` if public API, or document as internal
- **Expected Benefit:** Clearer public API

---

## Core Code (llm_do/)

### Critical (High impact, Low risk)

#### 1. Extract Method: `Worker.call()` method
- **Location:** `llm_do/runtime/worker.py:322-381` (60 lines)
- **Code Smell:** Method does input validation, model resolution, toolset wrapping, context spawning, agent building, and execution branching
- **Recommended Refactoring:** Extract `_validate_and_resolve_model()`, `_create_child_context()`, `_execute_with_events()`
- **Expected Benefit:** Each extracted method has single responsibility, easier to test and maintain

#### 2. Extract Method: `parse_worker_file()` function
- **Location:** `llm_do/runtime/worker_file.py:43-114` (72 lines)
- **Code Smell:** Long function handling regex matching, frontmatter parsing, toolsets parsing, server_side_tools parsing, compatible_models parsing
- **Recommended Refactoring:** Extract `_extract_frontmatter_and_instructions()`, `_parse_toolsets_section()`, `_parse_server_side_tools()`, `_parse_compatible_models()`
- **Expected Benefit:** Modular parsing, each section independently testable

#### 3. Dead Code: `clone_same_depth()` methods
- **Location:** `llm_do/runtime/context.py:291-301` and `llm_do/runtime/context.py:94-106`
- **Code Smell:** Methods defined in both `WorkerRuntime` and `CallFrame` but never called
- **Recommended Refactoring:** Remove both methods
- **Expected Benefit:** Less code to maintain

#### 4. Dead Code: Unused discovery functions
- **Location:** `llm_do/runtime/discovery.py:90-118` (`load_toolsets_from_files`) and `llm_do/runtime/discovery.py:120-150` (`load_workers_from_files`)
- **Code Smell:** Functions exported but never called; only `load_toolsets_and_workers_from_files` is used
- **Recommended Refactoring:** Remove or document as public API
- **Expected Benefit:** Reduced confusion, smaller API surface

### Important (Medium impact)

#### 5. Introduce Parameter Object: `run()` in cli/main.py
- **Location:** `llm_do/cli/main.py:262-330`
- **Code Smell:** 14 parameters! Groups include input/entry, approval policy, runtime options
- **Recommended Refactoring:** Create `RunInput` (files, prompt, entry_name, set_overrides) and `RunOptions` (model, on_event, verbosity, message_history); use existing `RunApprovalPolicy` instead of individual booleans
- **Expected Benefit:** Cleaner function signature, grouped configuration

#### 6. Introduce Parameter Object: Simplify `WorkerRuntime.__init__()`
- **Location:** `llm_do/runtime/context.py:169-210`
- **Code Smell:** 14 parameters with two initialization paths (config+frame OR individual params)
- **Recommended Refactoring:** Make constructor ONLY accept `config` and `frame`; move factory logic entirely to `from_entry()` class method
- **Expected Benefit:** Single initialization path, cleaner API

#### 7. Extract Class: `ToolDispatcher`
- **Location:** `llm_do/runtime/context.py:312-365`
- **Code Smell:** `WorkerRuntime.call()` method (54 lines) does tool lookup, event emission, and execution
- **Recommended Refactoring:** Extract `ToolDispatcher` class encapsulating tool resolution and dispatch logic
- **Expected Benefit:** `WorkerRuntime` becomes thinner facade, reusable tool dispatch

#### 8. Extract Class: `ToolEventEmitter`
- **Location:** `llm_do/runtime/worker.py:275-320`
- **Code Smell:** `_emit_tool_events()` method collects tool calls/returns from messages and emits events - separate concern from Worker execution
- **Recommended Refactoring:** Extract `ToolEventEmitter` class with `emit_from_messages()` method
- **Expected Benefit:** Separates event emission concern, independently testable

#### 9. Magic Numbers: Approval mode strings should be enum
- **Location:** `llm_do/runtime/approval.py:27` and multiple comparisons
- **Code Smell:** String literals `"prompt"`, `"approve_all"`, `"reject_all"` used for mode checking
- **Recommended Refactoring:** Create `ApprovalMode` enum with `PROMPT`, `APPROVE_ALL`, `REJECT_ALL` values
- **Expected Benefit:** Type safety, IDE autocomplete, no typo bugs

#### 10. Dead Code: Unused `usage` property
- **Location:** `llm_do/runtime/context.py:256-258`
- **Code Smell:** `usage` property and `UsageCollector` infrastructure exist but nothing retrieves the data
- **Recommended Refactoring:** Either implement usage reporting or remove the dead infrastructure
- **Expected Benefit:** Reduced complexity or completed feature

#### 11. Dead Code: Unused `WorkerFile.description` field
- **Location:** `llm_do/runtime/worker_file.py:35`
- **Code Smell:** Field parsed from frontmatter but never accessed
- **Recommended Refactoring:** Either use for help text/documentation or remove
- **Expected Benefit:** Cleaner data model or useful feature

### Minor (Low impact, Nice to have)

#### 12. Magic Number: Default max depth
- **Location:** `llm_do/runtime/context.py:64, 125, 178`
- **Code Smell:** `max_depth: int = 5` repeated three times
- **Recommended Refactoring:** Extract to `DEFAULT_MAX_DEPTH = 5` module constant
- **Expected Benefit:** Single source of truth

#### 13. Magic Number: Worker description truncation
- **Location:** `llm_do/runtime/worker.py:232`
- **Code Smell:** Hardcoded `[:200]` for instruction truncation in tool description
- **Recommended Refactoring:** Extract to `WORKER_DESCRIPTION_MAX_LENGTH = 200`
- **Expected Benefit:** Documented limit, easy to configure

#### 14. Magic Number: Top-level depth check
- **Location:** `llm_do/runtime/worker.py:104`
- **Code Smell:** `ctx.depth <= 1` for message history usage
- **Recommended Refactoring:** Extract to `TOP_LEVEL_DEPTH = 1`
- **Expected Benefit:** Self-documenting code

#### 15. Magic Number: Filesystem chunk sizes
- **Location:** `llm_do/toolsets/filesystem.py:199, 225, 247`
- **Code Smell:** Hardcoded `1024 * 1024`, `8192`, `65536` for file operations
- **Recommended Refactoring:** Extract to `SMALL_FILE_THRESHOLD`, `FILE_SEEK_CHUNK_SIZE`, `FILE_READ_CHUNK_SIZE`
- **Expected Benefit:** Documented thresholds, tunable performance

#### 16. Duplicated Environment Variable
- **Location:** `llm_do/cli/main.py:68` and `llm_do/models.py:26`
- **Code Smell:** `"LLM_DO_MODEL"` defined in both files
- **Recommended Refactoring:** Import `LLM_DO_MODEL_ENV` from `models.py` in CLI
- **Expected Benefit:** Single source of truth

#### 17. Verbosity Levels Should Be Constants
- **Location:** Multiple files use `0`, `1`, `2` for verbosity
- **Code Smell:** Magic numbers for verbosity levels scattered across codebase
- **Recommended Refactoring:** Define `VERBOSITY_QUIET = 0`, `VERBOSITY_NORMAL = 1`, `VERBOSITY_VERBOSE = 2`
- **Expected Benefit:** Self-documenting code, consistent usage

---

## Summary

| Category | UI Code | Core Code | Total |
|----------|---------|-----------|-------|
| Critical | 3 | 4 | 7 |
| Important | 8 | 7 | 15 |
| Minor | 6 | 6 | 12 |
| **Total** | **17** | **17** | **34** |

### Top 5 Recommended Actions

1. **Extract methods in `parse_event()`** - Biggest single function, high traffic code path
2. **Remove dead `clone_same_depth()` methods** - Zero-risk cleanup
3. **Extract methods in `Worker.call()`** - Core execution logic needs clarity
4. **Simplify `run()` function signature** - 14 parameters is excessive
5. **Create `ApprovalMode` enum** - Eliminates string literal bugs
