# Web Searcher Example

Demonstrates server-side tools with Anthropic's built-in web search.

## Running

```bash
export LLM_DO_MODEL="anthropic:claude-haiku-4-5"
llm-do examples/web_searcher "What are the latest developments in quantum computing?"
```

## What It Does

A research assistant that uses Anthropic's server-side web search tool to find current information and synthesize answers with citations.

## Project Structure

```
web_searcher/
├── main.agent      # Agent with server_side_tools
└── project.json    # Manifest
```

## Key Concepts

- **Server-side tools**: Tools executed by the model provider, not locally
- **web_search**: Built-in Anthropic tool for real-time web search
- **max_uses**: Limit on how many times the tool can be called (3 in this example)

## Agent Configuration

```yaml
server_side_tools:
  - tool_type: web_search
    max_uses: 3
```

## Note

Server-side tools are provider-specific. The `web_search` tool is available with Anthropic models.
