# Mistral Vibe

Minimal CLI coding agent by Mistral. Official tool from Mistral AI.

## Quick Facts

| | |
|---|---|
| **Repository** | https://github.com/mistralai/mistral-vibe |
| **Stars** | ~2,100 |
| **Primary use case** | Interactive chat-based code agent |
| **Python version** | 3.12+ |
| **License** | Apache 2.0 |
| **Activity** | Very active (official Mistral project, created Dec 2025) |

## Tech Stack

| Component | Library | Notes |
|-----------|---------|-------|
| **TUI framework** | Textual 1.0+ | Full TUI with custom widgets |
| **Terminal formatting** | Rich 14.x | Markdown, syntax highlighting |
| **HTTP client** | httpx 0.28+ | Async HTTP |
| **LLM integration** | mistralai 1.9+ | Native Mistral SDK |
| **Data validation** | pydantic 2.12+, pydantic-settings | Models, config |
| **Async files** | aiofiles 24.x | Async file operations |
| **File watching** | watchfiles 1.1+ | Hot reload? |
| **Process interaction** | pexpect 4.9+ | Shell/terminal handling |
| **Protocols** | agent-client-protocol 0.6+, mcp 1.14+ | ACP and MCP support |
| **Clipboard** | pyperclip 1.11+ | Copy/paste |

**Key observation:** Uses both **ACP** (Agent Client Protocol) and **MCP** (Model Context Protocol). This is forward-looking - these are emerging standards for agent interoperability.

## GUI Architecture

### Directory Structure
```
vibe/
├── __init__.py
├── cli/
│   ├── entrypoint.py         # CLI entry point (8.7 KB)
│   ├── commands.py           # Command definitions
│   ├── clipboard.py          # Clipboard ops
│   ├── history_manager.py    # Command history
│   ├── autocompletion/       # Path/command completion
│   ├── update_notifier/      # Version check
│   └── textual_ui/
│       ├── app.py            # Main TUI app (40 KB!)
│       ├── app.tcss          # Textual CSS (9.7 KB)
│       ├── handlers/         # Event handlers
│       ├── renderers/        # Custom rendering
│       └── widgets/          # Reusable widgets
├── core/
│   ├── agent.py              # Agent logic (35.5 KB)
│   ├── config.py             # Config management (18.6 KB)
│   ├── system_prompt.py      # Prompts (14.7 KB)
│   ├── middleware.py         # Request/response middleware
│   ├── interaction_logger.py # Logging
│   ├── types.py              # Type definitions
│   ├── tools/                # Tool implementations
│   ├── llm/                  # LLM interaction layer
│   └── prompts/              # Prompt templates
├── acp/                      # Agent Client Protocol
└── setup/                    # First-run setup
```

### Component Organization

The TUI is well-structured with clear separation:

| Directory | Purpose |
|-----------|---------|
| `handlers/` | Event handling (tool execution, streaming, etc.) |
| `renderers/` | Custom rendering (markdown, code blocks, diffs) |
| `widgets/` | Reusable UI components |

**`app.py` is 40KB** - this is the main TUI logic. Worth studying for patterns.

### Features (from README)

**Interactive Chat:**
- File read/write/patch operations
- Shell command execution in stateful terminals
- Code searching (grep/ripgrep)
- Todo list management

**Project Intelligence:**
- Automatic project structure scanning
- Git status awareness
- Context-aware responses

**CLI Experience:**
- Command and file path autocompletion
- Persistent command history
- Customizable themes
- Multi-line input support

**Control:**
- Tool execution approval system
- Custom system prompts
- MCP server integration
- Pattern-based tool enable/disable

## Borrowable Patterns

### 1. TUI Component Structure
**Effort:** Reference | **Value:** High

Their `handlers/`, `renderers/`, `widgets/` split is clean. We could adopt this:

```
llm_do/ui/
├── app.py
├── app.tcss
├── handlers/
│   ├── streaming.py
│   ├── approval.py
│   └── tool_result.py
├── renderers/
│   ├── markdown.py
│   └── json.py
└── widgets/
    ├── message_log.py
    └── input_area.py
```

### 2. Approval System
**Effort:** ~1 day | **Value:** High

They have "tool execution approval system" - worth studying how they present this in the TUI.

### 3. MCP Integration
**Effort:** Medium | **Value:** Future-proofing

MCP (Model Context Protocol) is an emerging standard. Their integration could be a reference for adding MCP support to llm-do.

### 4. Textual CSS Patterns
**Effort:** Reference | **Value:** Medium

Their `app.tcss` (9.7 KB) likely has good patterns for styling Textual apps.

### 5. Middleware Pattern
**Effort:** ~1 day | **Value:** Medium

`middleware.py` suggests request/response interception. Could be useful for:
- Token counting
- Request logging
- Response transformation

### 6. Config System
**Effort:** Reference | **Value:** Medium

18.6 KB config module suggests sophisticated configuration. They support:
- `config.toml` files
- Custom agents in `~/.vibe/`
- Pattern-based tool enable/disable

## Integration Options

### Us → Them (embed llm-do workers into Vibe)

**Approach:** Add llm-do as a tool in Vibe

Since Vibe supports MCP servers, we could potentially expose llm-do workers as an MCP server. This would allow Vibe users to delegate to llm-do workers.

### Them → Us (borrow Vibe components)

| Component | Feasibility | Notes |
|-----------|-------------|-------|
| TUI structure | High | Study their handlers/renderers/widgets split |
| Textual CSS | Easy | Reference their `app.tcss` |
| Approval UI | Medium | Study their tool approval patterns |
| MCP support | Future | Add MCP server capability to llm-do |
| Config system | Low priority | We have workshop.yaml |

## Key Differences from llm-do

| Aspect | Mistral Vibe | llm-do |
|--------|--------------|--------|
| **Focus** | Interactive Mistral chat | Multi-worker task execution |
| **LLM** | Mistral-only | Any (via pydantic-ai) |
| **Workers** | Single agent | Multi-worker delegation |
| **Sandboxing** | Pattern-based tool disable | Per-worker sandboxes |
| **Protocols** | ACP + MCP | Custom |
| **Configuration** | TOML + ~/.vibe/ | YAML workshop/worker files |

## Why This Project Matters

1. **Official Mistral tool** - Well-resourced, likely to be maintained
2. **Modern architecture** - ACP/MCP support, clean Textual structure
3. **Large TUI codebase** - 40KB app.py is a goldmine of patterns
4. **Active development** - Created Dec 2025, rapidly evolving

## Files to Study

| File | Size | Why |
|------|------|-----|
| `cli/textual_ui/app.py` | 40 KB | Main TUI patterns |
| `cli/textual_ui/app.tcss` | 9.7 KB | Styling patterns |
| `core/agent.py` | 35.5 KB | Agent architecture |
| `core/config.py` | 18.6 KB | Config patterns |
| `core/middleware.py` | 6.5 KB | Interception patterns |

## References

- Repository: https://github.com/mistralai/mistral-vibe
- ACP: https://agentclientprotocol.org/ (if exists)
- MCP: Model Context Protocol (Anthropic standard)

## Open Questions
- Which TUI patterns are lowest effort to port into llm-do?
- Is MCP support worth prototyping or should we focus on local tool UX first?
