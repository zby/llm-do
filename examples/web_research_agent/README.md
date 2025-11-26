# Web research & insight agent (llm-do example)

This example turns the architecture in `web_research_agent_architecture.md` into a runnable multi-worker workflow:
- **Orchestrator** searches the web, fans out extraction calls, consolidates, and writes reports.
- **Extractor** fetches a single URL and returns structured insights.
- **Consolidator** merges multi-source insights into prioritized findings.
- **Reporter** emits Markdown + JSON with citations for traceability.

## Prerequisites
- Install the repo: `pip install -e .`
- Set a model (inherits from CLI): `export MODEL=anthropic:claude-3-5-sonnet-20241022` (PowerShell: `$env:MODEL=...`) or `openai:gpt-4o`
- **Required**: `export SERPAPI_API_KEY=your_key` (PowerShell: `$env:SERPAPI_API_KEY=...`). Get a free API key at https://serpapi.com/

## Run
```bash
cd examples/web_research_agent
llm-do web_research_orchestrator "AI deployment in hospitals" --model $MODEL --approve-all
```

Outputs are written to `reports/{topic-slug}.md` and `reports/{topic-slug}.json`.

## Files
- `workers/web_research_orchestrator/worker.worker` — orchestrator definition + search tool
- `workers/web_research_extractor/worker.worker` — extractor definition + fetch tool
- `workers/web_research_consolidator.worker` — consolidates multi-source signals
- `workers/web_research_reporter.worker` — produces Markdown + JSON bundle
- `Worker instructions with Jinja2 templates` — worker instructions
- `schemas/models.py` — reference Pydantic models for the data contracts

## Notes
- Tools use standard library HTTP (no extra deps).
- `write_file` is approval-gated in the orchestrator; pass `--approve-all` for smooth runs.
- Keep topic slugs short and ASCII-safe; the orchestrator instructions handle slugging in-model.
