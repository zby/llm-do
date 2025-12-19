# Slash Commands

## Prerequisites
- [ ] 35-chat-support (need input handling during conversations)

## Goal
Add slash command support (`/help`, `/clear`, `/tool <name>`) to the TUI for user-initiated actions during conversations.

## Background

Slash commands provide a way for users to invoke actions that aren't part of the LLM conversation. This is foundational for manual tools (Task 50) which need a way to be invoked by the user.

## Tasks

### Phase 1: Command Parser
- [ ] Parse `/command args` from user input
- [ ] Distinguish slash commands from regular prompts
- [ ] Handle unknown commands gracefully

### Phase 2: Built-in Commands
- [ ] `/help` - Show available commands
- [ ] `/clear` - Clear conversation history
- [ ] `/quit` or `/exit` - Exit the TUI

### Phase 3: Extensible Command Registry
- [ ] Command registration interface
- [ ] Commands can be added by toolsets (for `/tool` command in Task 50)

## Current State
Not started.

## Notes
- Keep command set minimal initially
- This enables manual tools feature (Task 50)
