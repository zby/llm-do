# Web Research Agent

Multi-agent pipeline for comprehensive web research with structured output.

## Running

```bash
export LLM_DO_MODEL="anthropic:claude-haiku-4-5"
llm-do examples/web_research_agent "Impact of AI on healthcare in 2025"
```

Reports are written to `examples/web_research_agent/reports/`.

## What It Does

A four-agent pipeline that:

1. **Orchestrator** (`main.agent`) - Coordinates the research workflow
2. **Extractor** (`web_research_extractor.agent`) - Fetches and extracts insights from each URL
3. **Consolidator** (`web_research_consolidator.agent`) - Merges findings, identifies agreements/conflicts
4. **Reporter** (`web_research_reporter.agent`) - Generates final Markdown and JSON reports

## Output

For each research topic, generates:
- `reports/{topic-slug}.md` - Human-readable Markdown report
- `reports/{topic-slug}.json` - Structured JSON with findings, risks, recommendations

## Project Structure

```
web_research_agent/
├── main.agent                      # Orchestrator
├── web_research_extractor.agent    # URL content extractor
├── web_research_consolidator.agent # Findings merger
├── web_research_reporter.agent     # Report generator
├── tools.py                        # search_web, fetch_page, generate_slug
├── project.json
└── reports/                        # Output directory
```

## Key Concepts

- **Multi-agent pipeline**: Specialized agents for each stage
- **Structured handoff**: JSON data passed between agents
- **Citation tracking**: URLs preserved through the pipeline
- **Dual output**: Both human-readable and machine-parseable formats
