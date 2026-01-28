# Approvals Demo

Demonstrates the approval system for file write operations.

## Running

```bash
export LLM_DO_MODEL="anthropic:claude-haiku-4-5"
llm-do examples/approvals_demo "Had a great meeting with the team"
```

The TUI will prompt you to approve the file write operation.

## Running in Headless Mode

```bash
llm-do examples/approvals_demo --headless "Had a great meeting"
```

In headless mode with default `approval_mode: prompt`, the operation will be rejected. To auto-approve:

```bash
# Edit project.json to set "approval_mode": "approve_all"
llm-do examples/approvals_demo --headless "Had a great meeting"
```

## What It Does

A note-taking agent that appends timestamped entries to a log file. The `write_file` tool requires operator approval before execution.

## Project Structure

```
approvals_demo/
├── main.agent      # Note-taking agent
└── project.json    # Manifest with approval settings
```

## Key Concepts

- **Write approvals**: File operations require explicit approval
- **TUI prompts**: Interactive approval in terminal UI mode
- **Approval modes**: `prompt` (ask), `approve_all`, `reject_all`
