# Live Integration Tests

These tests make real API calls to LLM providers and are **excluded from the default test run** due to:
- Cost (API calls aren't free)
- Non-determinism (LLM responses vary)
- External dependencies (network, API availability)

## Running Live Tests

```bash
# Run all live tests
pytest tests/live/ -v

# Run tests for a specific example
pytest tests/live/test_greeter.py -v
pytest tests/live/test_calculator.py -v

# Run with extra output for debugging
pytest tests/live/ -v -s
```

## Required Environment Variables

| Variable | Required For | Notes |
|----------|--------------|-------|
| `ANTHROPIC_API_KEY` | Most tests | Primary provider, uses claude-haiku-4-5 for cost |
| `OPENAI_API_KEY` | Alternative | Used if Anthropic key not available |
| `SERPAPI_API_KEY` | web_research_agent | Free tier available at serpapi.com |

## Test Files

| File | Example | Features Tested |
|------|---------|-----------------|
| `test_greeter.py` | greeter | Basic LLM conversation, no tools |
| `test_calculator.py` | calculator | Custom Python tools |
| `test_code_analyzer.py` | code_analyzer | Shell tool with pattern-based approval |
| `test_web_searcher.py` | web_searcher | Server-side web search |
| `test_pitchdeck_eval.py` | pitchdeck_eval | Attachments, vision, worker delegation |
| `test_web_research_agent.py` | web_research_agent | Multi-worker orchestration, web tools |
| `test_whiteboard_planner.py` | whiteboard_planner | Vision, nested worker calls |

## Skip Conditions

Tests are automatically skipped if required environment variables are missing:

- `@skip_no_llm` - Skips if neither Anthropic nor OpenAI key is set
- `@skip_no_anthropic` - Skips if Anthropic key not set (for vision/PDF tests)
- `@skip_no_serpapi` - Skips if SerpAPI key not set

## Notes on Flakiness

LLM tests are inherently non-deterministic. If a test fails:

1. **Check the assertion** - Is it too specific? (e.g., exact word match vs contains)
2. **Try running again** - LLM responses vary
3. **Check API status** - Provider might be having issues
4. **Check your quota** - You might be rate-limited

## Adding New Live Tests

1. Create `test_<example_name>.py` in this directory
2. Import skip conditions from `conftest.py`
3. Use the `example_registry_factory` or specific `*_registry` fixtures
4. Use `approve_all_controller` fixture for non-interactive runs
5. Use `default_model` fixture or hardcode model for provider-specific tests
