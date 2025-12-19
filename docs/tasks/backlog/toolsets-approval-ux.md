# Toolsets and Approval UX Improvements

## Idea
Tighten toolset safety/UX by aligning approval checks, isolating custom tool modules, and improving schema guidance.

## Why
Current behavior can approve commands that later fail, allow tool module collisions, and reduce tool-call quality.

## Rough Scope
- Move shell metacharacter blocking into `needs_approval` for consistent UX.
- Namespace custom tool modules using a stable path hash to avoid collisions.
- Improve JSON schema generation for `Optional`/`Union` type hints.
- Avoid full-file loads in `read_file` when `max_chars` is set.

## Why Not Now
Touches multiple toolsets and requires careful regression testing.

## Trigger to Activate
Security/UX complaints or a focused toolset hardening effort.
