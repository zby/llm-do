# Delegation Tool Naming Safety

## Prerequisites
- [ ] None.

## Goal
Worker tool naming is collision-free and worker_create is robust in integrations.

## Tasks
- [ ] Reserve known provider tool names (web_search, web_fetch, etc.) in delegation collision checks.
- [ ] Consider introducing a prefixed worker tool namespace to eliminate collisions.
- [ ] Ensure `creation_defaults` is always set or safely defaulted in worker_create.

## Current State
Created from review notes; not started.

## Notes
- Origin: delegation/composition review notes.
