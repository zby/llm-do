# Toolsets and Approvals Review

## Context
Review of filesystem/custom/delegation/shell toolsets and approval controller behavior for correctness and UX consistency.

## Findings
- `ShellToolset.needs_approval` parses commands but does not check blocked metacharacters; commands with `|`/`;`/`$(` may appear approved and only fail later during execution, leading to inconsistent approval UX.
- `CustomToolset` module names use only the worker name; two workers with the same name from different directories will share the same `sys.modules` entry, risking tool leakage or stale imports.
- `_python_type_to_json_schema` does not handle `Optional[...]`/`Union[...]` properly (typing.Union path is not covered), so many type hints yield empty schemas and reduce tool-call guidance.
- `FileSystemToolset.read_file` loads the entire file before slicing, which can be memory-heavy for large files even when `max_chars` is small.

## Analysis
- Approval UX becomes inconsistent when a command is approved and then blocked during execution; this reduces trust and makes it harder to reason about policy.
- Module name collisions can leak or override tools when workers share names across different paths, which is especially risky in monorepos or generated worker directories.
- Weak schema generation degrades tool-call quality and can lead to malformed tool inputs because the model lacks structure hints.
- Reading full files before slicing is a performance and memory risk for large files and can amplify unexpected resource use.

## Possible Fixes
- Move metacharacter checks into `needs_approval` so blocked commands are rejected before approval is requested.
- Derive custom tool module names from a stable path hash (e.g., `tools_<worker_name>_<hash>`).
- Extend `_python_type_to_json_schema` to handle `Optional`/`Union` and basic `Literal` cases to improve schema fidelity.
- Stream file reads or read only the needed prefix when `max_chars` is set, avoiding full-file loads.

## Recommendations
1. Reject blocked shell metacharacters during approval to keep UX consistent.
2. Add path-based module names for custom tools to eliminate collisions.
3. Improve JSON schema generation for `Optional`/`Union` to increase tool-call reliability.
4. Avoid full-file loads in `read_file` when `max_chars` is small.

## Open Questions
- Should shell metacharacter checks move into `needs_approval` so blocked commands are rejected before approval?
- Should custom tool module names incorporate a stable path hash to avoid collisions?
- Is it worth improving JSON schema generation for `Optional`/`Union` to improve tool call quality?

## Conclusion
The main risks are inconsistent approval behavior and tool isolation. Addressing approval checks and module naming will improve safety, while schema and read optimizations improve reliability and performance.
