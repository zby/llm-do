# Multi-Instance Toolsets

## Goal
Support multiple instances of the same toolset type with different configurations (e.g., two browser instances, multiple shell configs).

## Background
Task 60 explicitly defers this: "Multi-instance toolsets (e.g., two browsers) deferred to future task"

The current design uses a flat namespace where each toolset type has a single instance. This task adds support for named instances.

## Use Cases
- Two browser toolsets with different profiles/configs
- Multiple shell toolsets with different rule sets
- Parallel file system toolsets for different sandboxes

## Design Considerations
- Naming scheme: `browser:profile1`, `shell:restricted`, or nested config?
- Tool name disambiguation: `shell.command` vs `restricted_shell.command`
- Worker file syntax for declaring multiple instances
- Registry changes to support instance lookup

## Tasks
- [ ] Design naming/disambiguation scheme
- [ ] Update worker file parser to support multi-instance declarations
- [ ] Update registry to handle instance lookups
- [ ] Update ToolsetToolEntry to include instance context
- [ ] Add tests for multi-instance scenarios
- [ ] Document the feature

## Current State
Not started. Low priority until single-instance pattern is validated.
