---
source: https://github.com/spacedriveapp/spacebot
captured: 2026-02-23
capture: web-fetch
type: web-page
---

# Spacebot: AI Agent for Teams and Communities

Author: spacedriveapp
Source: https://github.com/spacedriveapp/spacebot

**Repository:** spacedriveapp/spacebot
**Description:** An AI agent for teams, communities, and multi-user environments
**Stars:** 1.2k | **Forks:** 154
**License:** FSL-1.1-ALv2
**Language:** Rust
**Website:** [spacebot.sh](https://spacebot.sh)

## Overview

Spacebot is a concurrent AI agent framework designed for multi-user environments. Rather than processing everything sequentially in a single session, it splits functionality across specialized processes that work in parallel—channels handle conversation, branches manage thinking, workers execute tasks, and a cortex supervises the entire system.

## Core Architecture

The system uses five process types:

- **Channels:** User-facing LLM processes that never block, always responsive to messages
- **Branches:** Independent thinking forks that inherit channel context for analysis
- **Workers:** Specialized task executors (shell, file, browser, coding) spawned by branches
- **Compactor:** Programmatic monitor that prevents context overflow without interrupting conversation
- **Cortex:** System-wide supervisor managing memory, process health, and knowledge synthesis

## Key Capabilities

**Task Execution:**
- Shell commands with configurable timeouts
- File operations (read, write, list with auto-creation)
- Program execution with environment variables
- Headless browser automation with accessibility trees
- OpenCode integration for deep coding sessions
- Brave web search integration

**Messaging:**
Message coalescing detects rapid-fire bursts and batches them into single LLM turns. Native adapters support Discord, Slack, Telegram, Twitch, and Webchat with rich formatting, threading, reactions, and per-channel permissions.

**Memory System:**
Eight typed memory categories (Fact, Preference, Decision, Identity, Event, Observation, Goal, Todo) with graph edges (RelatedTo, Updates, Contradicts, CausedBy, PartOf). Hybrid recall merges vector similarity and full-text search via Reciprocal Rank Fusion. Memory bulletin provides periodic briefings injected into conversations.

**Model Routing:**
Four-level system selecting appropriate models per call—process-type defaults, task-type overrides, prompt complexity scoring, and fallback chains. Supports Anthropic, OpenAI, OpenRouter, Z.ai, Groq, Together, Fireworks, DeepSeek, xAI, Mistral, NVIDIA, MiniMax, Moonshot AI, Ollama, and custom OpenAI/Anthropic-compatible endpoints.

**Extensibility:**
- MCP (Model Context Protocol) integration for arbitrary tool access
- skills.sh registry for installing community skills
- Hot-reloadable configuration for live updates

**Scheduling:**
Cron jobs with natural language creation, clock-aligned intervals, active hours, per-job timeouts, and circuit breaker auto-disabling after failures.

## Deployment Options

- **spacebot.sh:** One-click hosted deployment
- **Self-hosted:** Single Rust binary, no dependencies
- **Docker:** Container with volume persistence

## Getting Started

**Requirements:** Rust 1.85+ and an LLM API key

```bash
git clone https://github.com/spacedriveapp/spacebot
cd spacebot
cargo build --release
```

Minimal configuration connects Discord, Slack, or other platforms with routing to any supported LLM provider.

## Design Philosophy

"Thinks, executes, and responds — concurrently, not sequentially. Never blocks. Never forgets." The architecture prevents the bottlenecks found in traditional single-threaded agent frameworks where conversation freezes during context compaction or task execution.

---

## Connection Discovery

### Discovery Trace

**Index exploration:**
- Read [notes/index.md](../notes/index.md) — scanned full directory for agent architecture, multi-agent, memory, concurrency themes
- Read [indexes.md](../indexes.md) — checked all indexes for membership relevance
- Read [approvals-index](../notes/approvals-index.md) — no direct relevance (Spacebot has no approval system)
- Read [pydanticai-upstream-index](../notes/pydanticai-upstream-index.md) — checked for runtime design overlap

**Semantic search** (via qmd query):
- query "concurrent agent architecture process types workers branches memory system context compaction" — top hits:
  - [voooooogel-multi-agent-future](../notes/research/voooooogel-multi-agent-future.md) (92%) — evaluated: STRONG, forking + hierarchy dissolution
  - [dynamic-agents-runtime-design](../notes/dynamic-agents-runtime-design.md) (42%) — evaluated: STRONG, static vs dynamic worker taxonomy
  - [experiment-runtime-without-worker](../notes/research/experiment-runtime-without-worker.md) (38%) — evaluated: weak, different problem (removing Worker class)
- query "multi-agent forking spawning dynamic runtime worker taxonomy" — top hits:
  - [voooooogel-multi-agent-future](../notes/research/voooooogel-multi-agent-future.md) (93%) — already evaluated
  - [dynamic-agents-runtime-design](../notes/dynamic-agents-runtime-design.md) (56%) — already evaluated
  - [subagent-onboarding-protocol](../notes/subagent-onboarding-protocol.md) (44%) — evaluated: STRONG, branch-as-fork implements implicit onboarding
- query "persistent memory learning knowledge retrieval vector search" — top hits:
  - [crystallisation-learning-timescales](../notes/crystallisation-learning-timescales.md) (88%) — evaluated: MODERATE, Spacebot's memory occupies unnamed position between timescales
  - [crystallisation-is-continuous-learning](../notes/crystallisation-is-continuous-learning.md) (51%) — evaluated: MODERATE, opaque vs inspectable learning substrate

**Keyword search:**
- grep "concurrent|parallel.*agent|process.*type" in notes/ — 8 files; evaluated voooooogel, toolset-state-spectrum, blocking_approvals (weak), execution-modes-user-stories (weak)
- grep "memory.*system|persistent.*memory|context.*window" — 5 files; evaluated crystallisation-learning-timescales, voooooogel, rlm-explained (weak), shesha-comparison (weak)
- grep "model.*routing|model.*select|complexity.*scor" — 2 files (type-catalog-review only); no genuine connection to Spacebot's model routing

**Additional candidates evaluated and rejected:**
- [agent-skills-unification](../notes/agent-skills-unification.md) — Spacebot's skills.sh is a distribution registry, this note is format alignment; too thin
- [pure-dynamic-tools](../notes/pure-dynamic-tools.md) — Spacebot workers are process types, not LLM-authored code; no genuine overlap
- [pure-python-vs-mcp-codemode](../notes/pure-python-vs-mcp-codemode.md) — Spacebot uses MCP as protocol, not in the "code mode" sense
- [container-security-boundary](../notes/container-security-boundary.md) — Spacebot runs as single binary with no sandbox model described
- [shesha-comparison](../notes/related_works/shesha-comparison.md) — different problem domain (document QA vs multi-user chat)

### Connections Found

**Strong connections:**

1. **[What Survives in Multi-Agent Systems](../notes/research/voooooogel-multi-agent-future.md)** — exemplifies and contradicts: Spacebot's "branches" (independent thinking forks inheriting channel context) are a production implementation of the forking pattern voooooogel predicts will survive. But Spacebot's five-process-type hierarchy (channels/branches/workers/compactor/cortex) is exactly the "hand-crafted hierarchy" voooooogel argues stronger models will dissolve. The tension is instructive: Spacebot bets that concurrency requirements make the process-type decomposition structural rather than dissolvable.

2. **[Dynamic Workers Runtime Design](../notes/dynamic-agents-runtime-design.md)** — contrasts: Spacebot hard-codes its worker taxonomy (shell, file, browser, coding) as static process types with predefined capabilities. llm-do's `agent_create`/`agent_call` lets the taxonomy emerge at runtime — the LLM decides what specialized workers to create based on the task. Same problem (how does an agent system decompose work?), opposite design bets: Spacebot predicts a fixed taxonomy covers the space; llm-do predicts it doesn't.

3. **[Subagent Onboarding Protocol](../notes/subagent-onboarding-protocol.md)** — exemplifies: Spacebot's branch-as-fork pattern is a production implementation of implicit onboarding. Branches inherit full channel context rather than receiving a single-shot prompt, sidestepping the explicit Q&A protocol this note proposes. The note's "Batch Onboarding (Fork Pattern)" section directly describes what Spacebot implements: one context-rich process forks into N instances, each with full conversational history. This provides evidence that the fork approach works at scale for the onboarding problem.

**Moderate connections:**

4. **[Crystallisation Is Continuous Learning](../notes/crystallisation-is-continuous-learning.md)** — contrasts: Spacebot's typed memory system (eight categories with graph edges, vector+FTS hybrid recall) and crystallisation's repo artifacts represent competing substrates for persistent agent learning. Spacebot's approach is opaque — you cannot diff a vector embedding or review what the system "learned." Crystallisation's approach is inspectable — every learning event is a versioned, testable commit. Both achieve "never forgets," but crystallisation additionally achieves "you can verify what it remembers."

5. **[Crystallisation: The Missing Middle](../notes/crystallisation-learning-timescales.md)** — extends: Spacebot's memory system occupies an unnamed position between in-context learning and crystallisation in the three-timescale framework. It persists across sessions (unlike in-context) but stores knowledge as opaque vector embeddings and structured records (unlike crystallisation's diffable repo artifacts). This suggests the timescale taxonomy may need a fourth category: structured-but-opaque persistence — more durable than context, less verifiable than artifacts.

6. **[llm-do vs PydanticAI runtime](../notes/llm-do-vs-pydanticai-runtime.md)** — contrasts: Both Spacebot and llm-do build runtime infrastructure on top of raw LLM calls, but optimize for orthogonal concerns. Spacebot's runtime contribution is concurrency (conversation never blocks during thinking or task execution). llm-do's is composition (unified tool/agent namespace enabling progressive stabilization). Neither addresses the other's primary concern, making them complementary reference points for the "what should a runtime add?" question.

7. **[Toolset state spectrum](../notes/toolset-state-spectrum-from-stateless-to-transactional.md)** — exemplifies: Spacebot's concurrent process types (channels, branches, workers running in parallel sharing a cortex supervisor) are a production instance of the intra-run interference problem this note catalogs. When a branch navigates a browser and a channel is simultaneously handling user messages, both through the same cortex, the state coordination challenge is exactly what categories 5-7 of the spectrum describe.

8. **[Inspectable substrate, not supervision, defeats the blackbox problem](../notes/inspectable-substrate-not-supervision-defeats-the-blackbox-problem.md)** — exemplifies (negatively): Spacebot's memory system is a concrete example of the opaque substrate problem this note identifies. Its eight typed memory categories with graph edges and vector embeddings store learning in a form that cannot be diffed, tested, or reviewed by agents or humans — the same opacity that Chollet warns about for weight-based learning, applied to structured memory. Crystallisation's repo artifacts counter this by choosing an inspectable substrate.
