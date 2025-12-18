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

**Deep-dive reports:**
- [mistral-vibe-borrowing-report.md](mistral-vibe-borrowing-report.md) - Detailed analysis of patterns to borrow from Mistral Vibe

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
| **State** | Singleton | Single Agent | Context passing |
| **Stars** | ~100 | ~2100 | - |
| **Recursive workers** | No | No | Yes |

---

## Borrowing Strategy: Best of Both

Each project excels in different areas. Here's what to borrow from each:

### From Mistral Vibe (TUI Excellence)

| Pattern | Why Vibe | Effort |
|---------|----------|--------|
| **Streaming markdown** | `MarkdownStream` is battle-tested, handles incremental rendering | Medium |
| **Modal approval UI** | Clean bottom-panel swap with async Future blocking | Medium |
| **Blinking indicators** | `●/○` toggle with green/red completion states | Easy |
| **Opacity-based CSS** | `$warning 15%` looks better than `$warning-darken-3` | Easy |
| **Generator events** | `async for event in agent.act()` - cleaner than callbacks | Medium |
| **Middleware pipeline** | Turn limits, cost limits, auto-compact - composable guards | Medium |

### From TunaCode (Practical Features)

| Pattern | Why TunaCode | Effort |
|---------|--------------|--------|
| **Token/cost tracking** | Simple, already pydantic-ai compatible | Easy |
| **Slash commands** | Clean registry pattern, familiar UX | Medium |
| **Output truncation** | Head+tail preservation shows context | Easy |
| **Session persistence** | JSON serialization of conversation state | Medium |
| **Shell escape** | `!cmd` for quick shell access | Easy |

### From Both (Security)

| Pattern | TunaCode | Mistral Vibe | Recommendation |
|---------|----------|--------------|----------------|
| **Dangerous patterns** | Regex patterns for fork bombs | Three-tier filtering | Use Vibe's approach (more sophisticated) |
| **Environment hardening** | Basic | `CI=true`, `PAGER=cat`, etc. | Use Vibe's approach |
| **Command splitting** | Simple | Splits on `&&`, `\|\|`, `;`, `\|` | Use Vibe's approach |

### Unique to Each (Not Both)

| Feature | Only In | Worth Borrowing? |
|---------|---------|------------------|
| **MCP/ACP protocols** | Mistral Vibe | Future consideration |
| **Research agent** | TunaCode | Maybe - read-only exploration mode |
| **Git branch safety** | TunaCode | Nice-to-have |
| **Project context scanning** | Mistral Vibe | Already have similar |
| **Theme system** | Both | Low priority |

---

## Implementation Priority

### Phase 1: Quick Wins (1-2 days)
From both projects - easy, high-value:

```
□ Token/cost tracking (TunaCode pattern)
□ Opacity-based CSS (Mistral Vibe pattern)
□ Output truncation head+tail (TunaCode pattern)
□ Environment hardening (Mistral Vibe pattern)
□ Blinking indicators (Mistral Vibe pattern)
```

### Phase 2: TUI Improvements (3-5 days)
Primarily from Mistral Vibe:

```
□ Streaming markdown widget
□ Modal approval UI
□ Generator-based events
□ Approval theme: warning not error
```

### Phase 3: UX Features (1 week)
Mix of both:

```
□ Slash commands framework (TunaCode)
□ Session persistence (TunaCode)
□ Middleware pipeline (Mistral Vibe)
□ Dangerous command detection (Mistral Vibe)
```

### Phase 4: Future (when needed)
```
□ MCP server support (Mistral Vibe reference)
□ Research/read-only mode (TunaCode reference)
```

---

## Architecture Compatibility Note

**Neither TunaCode nor Mistral Vibe supports recursive workers** - both use single-agent architectures:

- **TunaCode**: Global `SessionState` singleton
- **Mistral Vibe**: Single `Agent` class with `run()` method, tools have no context injection

**llm-do's `WorkerContext` pattern is unique** - workers can call other workers via `ctx.run_worker()`. This is our differentiator.

**Implication:** Borrow their TUI patterns, not their agent/tool architectures.
