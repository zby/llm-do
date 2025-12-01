# Web Searcher Example

A simple example demonstrating the `server_side_tools` feature with web search.

## Overview

This worker uses the LLM provider's built-in web search capability to answer questions with current information. The search is executed server-side by the provider (e.g., Anthropic, OpenAI), not locally.

## Usage

```bash
cd examples/web_searcher

# Using Anthropic Haiku (recommended for cost)
llm-do web_searcher "What are the latest developments in AI?" \
  --model anthropic:claude-haiku-4-5

# Using OpenAI (alternative)
llm-do web_searcher "What are the latest developments in AI?" \
  --model openai:gpt-4o-mini
```

## Configuration

The worker is configured with:

```yaml
server_side_tools:
  - tool_type: web_search
    max_uses: 3  # Limit searches per run (Anthropic)
```

## Provider Support

Web search is supported by:
- Anthropic Claude (with `max_uses`, `blocked_domains`, `allowed_domains`)
- OpenAI (via Responses API)
- Google
- Groq (compound models only)

## Notes

- Server-side tools execute on the provider's infrastructure, not locally
- No approval is required since execution happens remotely
- Use `max_uses` to limit API costs on supported providers
