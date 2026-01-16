# Worker Attachment Approval Options

## Context
We changed worker tool approvals to require prompting only when attachments are present. The manifest
(runtime config) had no way to override this behavior.

## Findings
- We want attachment approvals off by default, with a separate setting to enable them without
  requiring approval for every worker tool call.

## Open Questions
- None.

## Conclusion
Added manifest/runtime flags: `worker_calls_require_approval` and
`worker_attachments_require_approval`, both default false. Worker tool approvals are off by default;
attachments can be gated independently when needed.
