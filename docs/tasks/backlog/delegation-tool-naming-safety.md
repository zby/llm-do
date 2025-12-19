# Delegation Tool Naming Safety

## Idea
Prevent worker tool name collisions with provider/server-side tools and improve worker creation robustness.

## Why
Name collisions can cause ambiguous tool calls and confusing failures; missing creation defaults can break worker_create in integrations.

## Rough Scope
- Reserve known provider tool names (web_search, web_fetch, etc.) in delegation tool collision checks.
- Consider introducing a prefixed worker tool namespace to eliminate collisions entirely.
- Ensure `creation_defaults` is always set or safely defaulted in worker_create.

## Why Not Now
May require coordinated changes to tool naming and documentation.

## Trigger to Activate
New provider tools added or user reports of tool-name collisions.
