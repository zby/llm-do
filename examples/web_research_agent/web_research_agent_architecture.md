# Web Research & Insight Agent — Architecture & Implementation Plan

## 1. Overview
This document describes the design of a **real‑world, measurable, multi‑step automated research agent** built using **llm-do + Pydantic‑AI + multi‑worker orchestration**. The agent dynamically retrieves information from the web, extracts structured insights, consolidates analysis across sources, and generates an evidence‑based report.

Unlike a simple ChatGPT conversation, this agent:
- Works with **real‑time external data**, not static inputs
- Collects and analyzes **multiple independent sources**
- Produces **verifiable, ranked, structured output** (JSON + Markdown)
- Demonstrates **tool + LLM + workflow orchestration** capabilities
- Has a **clear and measurable goal**, satisfying real automation use cases

---

## 2. Workflow Diagram
```
User Topic Input (runtime)
        |
        v
(1) Orchestrator Worker
    - route workflow
    - call web search tool
        |
        v
(2) Web Search Tool
    - live search via API
    - returns URLs and titles
        |
        v
(3) Extract Worker (LLM)
    - fetch page content
    - extract insights, metrics, pros/cons, citations
        |
        v
(4) Consolidate Worker (LLM)
    - merge multi-source findings
    - identify consensus / conflicts
    - rank importance
        |
        v
(5) Report Writer Worker (LLM)
    - produce Markdown summary & structured JSON
```

---

## 3. Workers & Responsibilities
| Worker | Purpose |
|--------|---------|
| **Orchestrator** | Main controller, collects user input, calls tools, triggers child workers |
| **Web Search Tool** | Searches online content dynamically and returns URLs & snippets |
| **Extract Worker** | Reads content from URLs and extracts structured insights |
| **Consolidate Worker** | Merges information across sources, resolves conflicts, identifies priorities |
| **Report Writer** | Generates final deliverables (Markdown report + JSON structured summary) |

---

## 4. Example Output
### Markdown
```
# AI Deployment in Hospitals — Research Insights

## Key Findings
• Cost reduction: 15–28% improvement
• Regulatory compliance complexity
• Workforce augmentation benefits

## Evidence Sources
- https://example.com/article1
- https://example.com/report2
```

### JSON
```json
{
  "topic": "AI deployment in hospitals",
  "findings": ["cost savings", "workflow efficiency"],
  "risks": ["regulation", "integration cost"],
  "confidence": 0.82,
  "sources": ["url1", "url2"]
}
```

---

