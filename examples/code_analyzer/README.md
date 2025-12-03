# Code Analyzer

Analyze any codebase using safe shell commands. This example demonstrates **shell command execution** with pattern-based approval rules.

## Usage

Run from the directory you want to analyze:

```bash
# Analyze any project - just cd into it first
cd /path/to/your/project
llm-do /path/to/llm-do/examples/code_analyzer/workers/code_analyzer/worker.worker \
  "How many Python files are there?" \
  --model anthropic:claude-haiku-4-5

# Or with OpenAI
llm-do /path/to/llm-do/examples/code_analyzer/workers/code_analyzer/worker.worker \
  "Find all TODO comments" \
  --model openai:gpt-4o-mini
```

Shell commands run from your **current directory**, so the worker analyzes whatever codebase you're in.

## Example Session

```bash
$ cd ~/my-project
$ llm-do ~/llm-do/examples/code_analyzer/workers/code_analyzer/worker.worker \
    "How many Python files and total lines of code?" \
    --model anthropic:claude-haiku-4-5

> Using tool: shell
  Command: find . -name "*.py" -type f

[Lists Python files]

> Using tool: shell
  Command: wc -l ./src/main.py ./src/utils.py ...

There are 12 Python files with 1,847 total lines of code.
```

## What This Shows

- **Shell tool integration**: Execute shell commands from within workers
- **Pattern-based approval**: `shell_rules` allow specific commands without prompts
- **Security defaults**: Block all commands by default, allow only safe ones
- **Portable execution**: Analyze any directory by running from there

## Shell Rules Configuration

The worker defines explicit rules for allowed commands in the `toolsets.shell` config:

```yaml
toolsets:
  shell:
    rules:
      - pattern: wc           # Count lines, words, bytes
        approval_required: false
      - pattern: find         # Locate files
        approval_required: false
      - pattern: grep         # Search patterns
        approval_required: false
      - pattern: ls           # List directories
        approval_required: false
      - pattern: cat          # Display files
        approval_required: false
      - pattern: git log      # Git history
        approval_required: false
      # ... more safe commands
    # No default = block everything else
```

**How it works:**
- Commands matching a pattern (e.g., `wc -l file.py`) are auto-approved
- Unmatched commands are blocked by default
- Shell metacharacters (`|`, `>`, `<`, `;`, `&`) are **always blocked** for security

## Security

### Allowed Commands (read-only)
- `ls`, `cat` - view files and directories
- `wc`, `find`, `grep` - analysis tools
- `head`, `tail`, `sort`, `uniq` - text processing
- `git log`, `git diff`, `git show`, `git status` - read git history

### Blocked
- All other commands (rm, mv, cp, etc.)
- Shell metacharacters - no pipes, redirects, or command chaining
- The LLM must run commands individually and combine results itself

## Sample Queries

```bash
# File statistics
"How many Python files are there?"
"What are the largest files by line count?"
"Count total lines of code"

# Code search
"Find all TODO comments"
"Search for uses of 'async def'"
"Find files containing 'import requests'"

# Git analysis
"Show the most recent 5 commits"
"What files changed in the last commit?"
"Show git status"
```

## Notes

- Commands run from your current working directory
- Output is truncated at 50KB to prevent token overflow
- Commands timeout after 30 seconds by default
- No pipes means the LLM counts/processes results itself
