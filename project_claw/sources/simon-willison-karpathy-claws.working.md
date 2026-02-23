---
source: https://simonwillison.net/2026/Feb/21/claws/
captured: 2026-02-22
capture: fetch
type: blog-post
---

# Andrej Karpathy talks about "Claws"

Author: Simon Willison
Post: https://simonwillison.net/2026/Feb/21/claws/
Created: 2026-02-21

[Andrej Karpathy talks about "Claws"](https://twitter.com/karpathy/status/2024987174077432126). Andrej Karpathy tweeted a mini-essay about buying a Mac Mini ("The apple store person told me they are selling like hotcakes and everyone is confused") to tinker with Claws:

> I'm definitely a bit sus'd to run OpenClaw specifically [...] But I do love the concept and I think that just like LLM agents were a new layer on top of LLMs, Claws are now a new layer on top of LLM agents, taking the orchestration, scheduling, context, tool calls and a kind of persistence to a next level.
>
> Looking around, and given that the high level idea is clear, there are a lot of smaller Claws starting to pop out. For example, on a quick skim NanoClaw looks really interesting in that the core engine is ~4000 lines of code (fits into both my head and that of AI agents, so it feels manageable, auditable, flexible, etc.) and runs everything in containers by default. [...]
>
> Anyway there are many others - e.g. nanobot, zeroclaw, ironclaw, picoclaw (lol @ prefixes). [...]
>
> Not 100% sure what my setup ends up looking like just yet but Claws are an awesome, exciting new layer of the AI stack.

Andrej has an ear for fresh terminology (see [vibe coding](https://simonwillison.net/2025/Mar/19/vibe-coding/), [agentic engineering](https://simonwillison.net/2026/Feb/11/glm-5/)) and I think he's right about this one, too: "Claw" is becoming a term of art for the entire category of OpenClaw-like agent systems - AI agents that generally run on personal hardware, communicate via messaging protocols and can both act on direct instructions and schedule tasks.

It even comes with an established emoji 🦞

Karpathy's description of Claws as "a new layer on top of LLM agents, taking the orchestration, scheduling, context, tool calls and a kind of persistence to a next level" is essentially the productized form of [what survives in multi-agent systems](../../../docs/notes/research/voooooogel-multi-agent-future.md) -- filesystem-based collaboration, agent spawning mechanisms, and persistent cross-session state, now packaged as installable systems running on personal hardware.

The emphasis on NanoClaw running "everything in containers by default" with a ~4000-line auditable core validates the [container security boundary](../../../docs/notes/container-security-boundary.md) design direction -- containers as the single battle-tested isolation mechanism, with auditability coming from a codebase small enough for both humans and AI agents to comprehend.

The "persistence" dimension of Claws -- agents that maintain state across sessions and schedule tasks autonomously -- sits at the intersection of [crystallisation's three timescales](../../../docs/notes/crystallisation-learning-timescales.md) and [dynamic agent creation](../../../docs/notes/dynamic-agents-runtime-design.md). Where llm-do's dynamic agents are session-scoped and experimental, Claws push toward persistent, always-running agents that accumulate context over time. This is crystallisation's third timescale (across-session adaptation) applied to the agent infrastructure itself, not just the artifacts agents produce.

The simultaneous emergence of koylanai's [Personal Brain OS](./the-file-system-is-the-new-database-how-i-built-a-personal-os-for-ai-a-2025286163641118915.working.md) and Karpathy's endorsement of Claws suggests a convergence: personal AI systems that run locally, persist across sessions, and use the filesystem as their primary interface are becoming a recognized category rather than individual experiments.

Tags: definitions, ai, andrej-karpathy, generative-ai, llms, ai-agents, openclaw

---

Relevant Notes:
- [What Survives in Multi-Agent Systems](../../../docs/notes/research/voooooogel-multi-agent-future.md) — Claws are the productized form of voooooogel's predictions: persistent multi-agent systems with filesystem collaboration, spawning, and model-discovered patterns, now running on personal hardware
- [container-security-boundary](../../../docs/notes/container-security-boundary.md) — NanoClaw's "runs everything in containers by default" validates containers as the natural security boundary for agent execution
- [crystallisation-learning-timescales](../../../docs/notes/crystallisation-learning-timescales.md) — Claws extend crystallisation's third timescale (across-session adaptation) from artifacts to agent infrastructure itself, with persistent scheduling and context
- [dynamic-agents-runtime-design](../../../docs/notes/dynamic-agents-runtime-design.md) — Claws represent the persistent end of the spectrum that llm-do's session-scoped dynamic agents explore at the ephemeral end
- [Personal Brain OS](./the-file-system-is-the-new-database-how-i-built-a-personal-os-for-ai-a-2025286163641118915.working.md) — sibling snapshot: both describe the emergence of personal AI systems that run locally with filesystem-based memory, suggesting a convergent category
