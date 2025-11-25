# Code Analyzer (llm-do shell tool example)

This example demonstrates **shell command execution** with pattern-based approval rules. The worker analyzes codebases using safe, read-only shell commands.

## What This Shows

- **Shell tool integration**: Execute shell commands from within workers
- **Pattern-based approval**: `shell_rules` allow specific commands without user approval
- **Security defaults**: Block all commands by default, allow only safe ones
- **Read-only operations**: All commands are non-destructive analysis tools

## Shell Rules Configuration

The worker defines explicit rules for allowed commands:

```yaml
shell_rules:
  - pattern: "wc"           # Count lines, words, bytes
    approval_required: false
  - pattern: "find"         # Locate files
    approval_required: false
  - pattern: "grep"         # Search patterns
    approval_required: false
  # ... more safe commands

shell_default:
  allowed: false            # Block everything else
  approval_required: true
```

**How it works:**
- Commands matching a pattern (e.g., `wc -l file.py`) are auto-approved
- Unmatched commands are blocked by default
- Shell metacharacters (`|`, `>`, `<`, `;`, `&`) are **always blocked for security**
- The `repo` sandbox provides read access to the repository root

## Prerequisites

```bash
pip install -e .
export MODEL=anthropic:claude-3-5-sonnet-20241022
```

## Usage

Run from the llm-do repository root to analyze the codebase itself:

```bash
cd examples/code_analyzer

# Count Python files
llm-do code_analyzer "How many Python files are in this codebase?"

# Analyze code volume
llm-do code_analyzer "Count total lines of code in the llm_do/ directory"

# Find patterns
llm-do code_analyzer "Find all TODO comments in Python files"

# Git analysis
llm-do code_analyzer "Show the most recent commit"

# Complex query
llm-do code_analyzer "What are the largest Python files by line count?"
```

## Example Session

```
$ llm-do code_analyzer "How many Python files are in the llm_do/ directory?"

> Using tool: shell
  Command: find repo/llm_do -name "*.py" -type f

[Lists all Python files]

> Agent counts the results

There are 23 Python files in the llm_do/ directory.
```

Note: Pipes are blocked for security, so the agent runs `find` and counts results itself.

## Key Features

### 1. Pattern Matching
Shell rules match command prefixes:
- `pattern: "wc"` matches `wc`, `wc -l file.py`, `wc -w *.txt`
- First matching rule wins

### 2. Security by Default
- Only explicitly allowed commands can run
- Shell metacharacters (`|`, `>`, `<`, `;`, `&`) are blocked to prevent injection
- Commands run with `shell=False` (no shell interpretation)
- No pipes means the LLM must combine results programmatically

### 3. Read-Only Safety
All allowed commands are read-only:
- ✅ `wc`, `find`, `grep` - analysis tools
- ✅ `git log`, `git show` - read git history
- ❌ `rm`, `mv`, `git commit` - blocked by default

## Comparison to Other Examples

| Example | Focus | Shell Tool | Custom Tools |
|---------|-------|------------|--------------|
| **code_analyzer** | Shell commands | ✅ Pattern rules | ❌ |
| calculator | Custom Python tools | ❌ | ✅ |
| web_research_agent | Multi-worker orchestration | ❌ | ✅ HTTP tools |

## Advanced: Sandbox Path Validation

For write operations, you can restrict commands to specific sandboxes:

```yaml
shell_rules:
  - pattern: "mkdir"
    sandbox_paths: ["workspace"]  # Only allow in workspace/
    approval_required: false
```

See the documentation for details on `sandbox_paths` validation.

## Notes

- Commands run from the repository root directory
- Output is truncated at 50KB to prevent token overflow
- Commands timeout after 30 seconds by default
- This example has no custom tools - it uses only the built-in shell tool
