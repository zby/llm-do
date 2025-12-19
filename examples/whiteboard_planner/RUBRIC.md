# Whiteboard Interpretation Rubric

Your goal is to transform a photo of a whiteboard session into a structured, actionable project plan.

## 1. Extraction & Interpretation
- **Read everything**: Extract all legible text, diagrams, and notes.
- **Interpret layout**: Use spatial organization (groupings, arrows, lists) to infer relationships.
- **Infer context**: If the whiteboard is messy, make reasonable assumptions based on standard software engineering or project management practices.

## 2. Structure the Plan
Organize the extracted information into these sections:

### High-level Summary
- What is the project?
- What is the main goal?

### Epics / Workstreams
- Group related tasks into 3-7 logical "Epics" or "Workstreams".
- For each Epic:
  - **Goal**: A one-sentence summary of what this epic achieves.
  - **Tasks**: List specific actionable items.
    - Assign a priority (P0 = critical, P1 = important, P2 = nice to have).
    - Note dependencies if implied by arrows or order.

### Timeline (Rough)
- Propose a timeline based on the complexity of tasks.
- Break it down by weeks or sprints (e.g., "Week 1-2: Foundation").

### Open Questions / Risks
- List any ambiguities, missing info, or potential blockers.

## 3. Style Guidelines
- **Be specific**: Don't just say "Backend work", say "Set up API endpoints for user auth".
- **Be professional**: Convert shorthand/slang into clear professional language.
- **Markdown only**: Output clean, nested markdown.
