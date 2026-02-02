# Examples

Examples organized by concept, from simple to advanced.

## Getting Started

| Example | What it demonstrates |
|---------|---------------------|
| [`greeter/`](greeter/) | Minimal single-agent setup—no tools, just a friendly prompt |

## Custom Tools

| Example | What it demonstrates |
|---------|---------------------|
| [`calculator/`](calculator/) | Python tools for math operations (factorial, fibonacci, add, multiply) |
| [`data_processor/`](data_processor/) | Data transformation tools (CSV formatting, statistics) |

## Custom Providers

| Example | What it demonstrates |
|---------|---------------------|
| [`custom_provider/`](custom_provider/) | Register a custom provider for use with `LLM_DO_MODEL` |

## File Operations & Approvals

| Example | What it demonstrates |
|---------|---------------------|
| [`approvals_demo/`](approvals_demo/) | Approval workflow for file system writes—human confirmation for sensitive actions |
| [`file_organizer/`](file_organizer/) | LLM semantic decisions + Python sanitization tools for file renaming |
| [`code_analyzer/`](code_analyzer/) | Read-only shell access with pre-approved commands (ls, find, grep, wc) |

## Progressive Stabilizing

The pitchdeck examples show the same task at different stabilization levels—a concrete demonstration of "extend with LLMs, stabilize with code."

| Example | What it demonstrates |
|---------|---------------------|
| [`pitchdeck_eval/`](pitchdeck_eval/) | All LLM: multi-agent delegation, PDF attachments, orchestrator pattern |
| [`pitchdeck_eval_stabilized/`](pitchdeck_eval_stabilized/) | Extracted tools: helper toolsets for common file operations |
| [`pitchdeck_eval_code_entry/`](pitchdeck_eval_code_entry/) | Python entry: orchestration in code, agents handle reasoning |
| [`pitchdeck_eval_direct/`](pitchdeck_eval_direct/) | Direct API: three abstraction levels without CLI |

## Recursive Patterns

| Example | What it demonstrates |
|---------|---------------------|
| [`recursive_summarizer/`](recursive_summarizer/) | Hierarchical summarization—split, summarize chunks, merge recursively |
| [`recursive_task_decomposer/`](recursive_task_decomposer/) | Task breakdown across recursion depths with structured output |

## Web & Research

| Example | What it demonstrates |
|---------|---------------------|
| [`web_searcher/`](web_searcher/) | Server-side tools (native web_search) for live data |
| [`web_research_agent/`](web_research_agent/) | Multi-agent research pipeline: search → extract → consolidate → report |

## Orchestration Patterns

| Example | What it demonstrates |
|---------|---------------------|
| [`orchestrating_tool/`](orchestrating_tool/) | Tool that orchestrates agents—encapsulates multi-agent pipelines in Python |

## Advanced Patterns

| Example | What it demonstrates |
|---------|---------------------|
| [`whiteboard_planner/`](whiteboard_planner/) | Multi-modal input: reads whiteboard images, generates project plans |
| [`rlm_repl/`](rlm_repl/) | Persistent Python REPL context for querying large data |

## Running Examples

From the project root:

```bash
# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Run any example
llm-do examples/greeter/project.json "Hello!"
llm-do examples/calculator/project.json "What is 10 factorial?"
llm-do examples/pitchdeck_eval/project.json
```

Some examples require input files (pitchdeck PDFs, whiteboard images). Check each example's `project.json` for expected inputs.
