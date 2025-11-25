# Web research & insight agent (llm-do example)

This example turns the architecture in `web_research_agent_architecture.md` into a runnable multi-worker workflow:
- **Orchestrator** searches the web, fans out extraction calls, consolidates, and writes reports.
- **Extractor** fetches a single URL and returns structured insights.
- **Consolidator** merges multi-source insights into prioritized findings.
- **Reporter** emits Markdown + JSON with citations for traceability.

## Prerequisites
- Install the repo: `pip install -e .`
- Set a model (inherits from CLI): `export MODEL=anthropic:claude-3-5-sonnet-20241022` (PowerShell: `$env:MODEL=...`) or `openai:gpt-4o`
- Optional but recommended for better search: `export SERPAPI_API_KEY=your_key` (PowerShell: `$env:SERPAPI_API_KEY=...`; falls back to DuckDuckGo instant answer API when unset)

## Run
```bash
cd examples/web_research_agent
llm-do web_research_orchestrator "AI deployment in hospitals" --model $MODEL --approve-all
```

Outputs are written to `reports/{topic-slug}.md` and `reports/{topic-slug}.json`.

## Files
- `workers/web_research_orchestrator/worker.yaml` — orchestrator definition + search tool
- `workers/web_research_extractor/worker.yaml` — extractor definition + fetch tool
- `workers/web_research_consolidator.yaml` — consolidates multi-source signals
- `workers/web_research_reporter.yaml` — produces Markdown + JSON bundle
- `prompts/*.jinja2` — worker instructions
- `schemas/models.py` — reference Pydantic models for the data contracts

## Notes
- Tools use standard library HTTP (no extra deps). They respect `SERPAPI_API_KEY` when present, otherwise default to DuckDuckGo JSON.
- `write_file` is approval-gated in the orchestrator; pass `--approve-all` for smooth runs.
- Keep topic slugs short and ASCII-safe; the orchestrator instructions handle slugging in-model.
