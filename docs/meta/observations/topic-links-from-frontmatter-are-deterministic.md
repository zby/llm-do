---
description: The areas-to-Topics mapping is mechanical — a concrete stabilization candidate now implemented as scripts/sync_topic_links.py
type: insight
areas: [kb-design]
status: current
---

# Topic links from frontmatter are deterministic

The `areas:` frontmatter field lists which indexes a note belongs to. The Topics footer section contains markdown links to those same indexes. Currently `/connect` generates these with LLM judgment, but the mapping is mechanical: read `areas`, write links.

This is a concrete stabilization candidate — replace a stochastic step with a Python script that reads frontmatter and generates footer links. The frontmatter isn't visible in markdown preview, so the footer links matter for browsing.

See [storing LLM outputs is stabilization](../../notes/storing-llm-outputs-is-stabilization.md) for the general pattern.

Topics:
- [kb-design](./../kb-design.md)
