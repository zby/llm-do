# Other Python LLM Assistants

Notes on other Python-based LLM CLI tools we can learn from.

## Purpose

We analyze these tools to:
1. **Borrow GUI patterns** - Our TUI is basic, theirs are mature
2. **Understand architectures** - How do others structure async TUIs?
3. **Find integration points** - Can we embed llm-do workers into their UIs?

LLM access patterns are **least important** - we're committed to pydantic-ai.

## Note Structure

Each tool should have notes covering:

### Quick Facts
- Repository URL, stars, activity level
- Primary use case (interactive chat? task runner? code agent?)
- Python version requirements
- License

### Tech Stack (most important for borrowing)
| Component | What to document |
|-----------|------------------|
| TUI framework | Textual / Rich / curses / prompt_toolkit? |
| CLI framework | typer / click / argparse? |
| LLM integration | pydantic-ai / langchain / raw API? |
| Async pattern | asyncio throughout? sync main loop with async calls? |
| State management | Singleton? Context passing? Global state? |

### GUI Architecture
- Component hierarchy (how is the TUI structured?)
- Event system (custom events? message passing?)
- Streaming response handling
- Input handling (multiline? slash commands?)
- Approval/confirmation UI patterns

### Borrowable Patterns
For each feature worth borrowing:
- What it does
- File locations in their codebase
- Effort estimate to adapt
- Dependencies it would bring

### Integration Options
- **Us → Them**: How to embed llm-do workers into their UI
- **Them → Us**: How to borrow their components into llm-do

## Tools Documented

| Tool | Focus | TUI Framework | Notes |
|------|-------|---------------|-------|
| [TunaCode](tunacode.md) | Interactive code agent | Textual 4.x | MIT, ~100 stars |
| [Mistral Vibe](mistral-vibe.md) | Chat interface | Textual 1.x | Apache 2.0, ~2100 stars, official Mistral |

**Integration notes** (separate from analysis):
- [tunacode-integration.md](tunacode-integration.md) - How to embed llm-do workers INTO TunaCode

## Priority for Borrowing

1. **TUI structure** - handlers/renderers/widgets split (Mistral Vibe)
2. **Textual CSS patterns** - Styling reference (both)
3. **Token tracking** - Cost display (TunaCode)
4. **Slash commands** - Command parsing (TunaCode)
5. **Approval UI** - Tool confirmation patterns (both)

## Comparison

| Aspect | TunaCode | Mistral Vibe | llm-do |
|--------|----------|--------------|--------|
| **TUI size** | Medium | Large (40KB app.py) | Small |
| **LLM** | pydantic-ai (multi) | mistralai (Mistral only) | pydantic-ai |
| **Protocols** | None | ACP + MCP | Custom |
| **State** | Singleton | ? | Context passing |
| **Stars** | ~100 | ~2100 | - |
