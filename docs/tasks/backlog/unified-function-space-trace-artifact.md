# Unified Function Space Trace Artifact and Replay

## Idea
Introduce a first-class execution trace artifact (JSONL) for unified function space calls, capturing call stack, approvals, tool args/results (with redaction controls), and model parameters, plus a replay mode to re-run with stubbed or recorded tool outputs.

## Why
Debugging nested calls and tool failures is hard without a transparent call stack and reproducible traces. A replayable trace reduces model variability during investigations and makes failures actionable.

## Rough Scope
- Define trace schema (JSONL events) for worker/tool call stack, approvals, args/results, model config.
- Add redaction controls for sensitive args/results.
- Implement trace emission across worker and tool execution paths.
- Add replay mode to stub tools or use recorded outputs.
- Document trace artifact location, retention, and CLI usage.

## Why Not Now
Needs clear boundaries for recursion limits, privacy/redaction policy, and storage/retention decisions.

## Trigger to Activate
Repeated debugging pain around nested calls, user requests for trace visibility, or a concrete incident requiring replayable traces.
