# Code Analyzer Example

Demonstrates safe shell command execution for codebase analysis.

## Running

```bash
export LLM_DO_MODEL="anthropic:claude-haiku-4-5"
cd /path/to/your/project
llm-do /path/to/llm-do/examples/code_analyzer "Analyze this codebase"
```

Or analyze a specific aspect:

```bash
llm-do examples/code_analyzer "Count lines of Python code and find TODO comments"
```

## What It Does

A code analysis assistant that uses read-only shell commands to gather statistics about codebases. It can count lines, find files, search for patterns, and inspect git history.

## Available Commands

Pre-approved read-only commands:
- `ls`, `cat`, `wc`, `find`, `grep`, `head`, `tail`, `sort`, `uniq`
- `git log`, `git diff`, `git show`, `git status`

All other commands and shell metacharacters (`|`, `>`, `;`, `&`) are blocked.

## Project Structure

```
code_analyzer/
├── main.agent      # Analysis agent with shell_readonly toolset
└── project.json    # Manifest
```

## Key Concepts

- **Restricted shell**: Only safe, read-only commands are allowed
- **No pipes**: Shell metacharacters are blocked for security
- **Pattern searching**: Use `grep -e` for multiple patterns instead of regex alternation
