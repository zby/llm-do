# Worker Pitfalls

Common issues when creating or modifying workers.

## Sandbox Configuration

Forgetting to configure sandboxes leads to runtime `KeyError`. Always declare sandboxes explicitly with the minimal access needed.

## Approval Rules

Approval rules default to auto-approve. Lock down `tool_rules` for critical workers that handle sensitive operations.

## Model Inheritance

Model selection follows inheritance: worker → caller → CLI flag. Set `model` explicitly in YAML if a worker needs a specific model regardless of how it's invoked.
