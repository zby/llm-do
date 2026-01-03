# Execution Modes: User Stories

## Mode Philosophy

**Proposal: Chat as default** (like other AI assistants)
- `llm-do` → starts chat mode
- `llm-do --headless "prompt"` or `llm-do --run "prompt"` → headless mode
- Aligns with user expectations from ChatGPT, Claude, etc.

Two general modes:
1. **Chat (default)** - interactive TUI with multi-turn conversations
2. **Headless** - explicit flag, single-turn, for scripting/automation

---

## Headless Mode User Stories

**As a developer automating tasks...**
- I want to run a worker from a script/CI pipeline so that I can automate repetitive tasks
- I want predictable approval behavior (approve-all/reject-all) so that scripts run unattended
- I want JSON output so that I can parse results programmatically
- I want to pipe input and capture output so that I integrate with shell workflows

**As a developer testing workers...**
- I want to quickly run a worker with a prompt so that I can verify it works
- I want verbose output so that I can debug tool calls and responses

**As a researcher running batch summaries...**
- I want to summarize a folder of papers without prompts so that I can automate literature reviews
- I want consistent output formats (Markdown/JSON) so that I can ingest results into my notes
- I want citations and source IDs in the output so that I can trace claims back to papers

**As an investor analyst running a report...**
- I want to extract KPIs from filings in headless mode so that I can automate weekly updates
- I want structured output (tables/JSON/CSV) so that I can compare across companies
- I want provenance attached to each number so that I can defend conclusions

---

## Chat Mode User Stories

**As a developer working on a task...**
- I want to have a conversation with a worker so that I can iteratively refine my request
- I want to see tool calls and approve/reject them so that I stay in control
- I want message history preserved so that context builds across turns

**As a developer exploring/prototyping...**
- I want to start chatting without specifying a worker so that I can quickly ask questions
- I want to load a worker mid-conversation so that I can add capabilities when needed
- I want to switch workers so that I can use the right tool for each sub-task

**As a developer with multiple workers...**
- I want to easily select from available workers so that I don't need to remember file paths
- I want a default worker for my project so that I can just type `llm-do`

**As a developer debugging a worker...**
- I want to test my worker interactively so that I can see how it responds to various inputs
- I want to reload a worker after editing so that I can iterate quickly

**As a researcher exploring literature...**
- I want to search for related work and summarize key papers so that I can build a quick survey
- I want to bookmark sources and see citations inline so that I can keep track of evidence
- I want to refine queries interactively so that I can follow new threads

**As an investor analyst investigating a company...**
- I want to ask targeted questions and inspect sources so that I can validate claims
- I want to track assumptions and caveats so that I can separate facts from hypotheses
- I want a watchlist of companies/topics so that I can revisit them over time

---

## Tool Call Approval Scenarios

### Scenario 1: Simple chat, no worker
```
$ llm-do
> What's the capital of France?
Paris is the capital of France.
```
No tools, no approvals needed. Pure conversation.

### Scenario 2: Chat with worker, first tool call
```
$ llm-do shell.worker
> List files in current directory
[Tool call: shell.run("ls -la")]
? Approve this tool call? [y/n/always/never]
> y
[output of ls -la]
```
User sees tool call, decides to approve.

### Scenario 3: Session-level approval
```
> y (always for this tool)
```
User approves and says "don't ask again for this tool in this session."
Reduces approval fatigue for trusted tools.

### Scenario 4: Worker calls sub-worker
```
$ llm-do orchestrator.worker
> Research and summarize topic X
[Tool call: researcher.call("find sources on X")]
  [Sub-tool call: web_search("topic X")]
  ? Approve web_search? [y/n/always]
```
Question: Should sub-worker tool calls bubble up for approval? Or does approving the parent imply trusting its tool choices?

### Scenario 5: Loading a worker mid-conversation
```
$ llm-do
> I need to analyze some data
I can help with that. What kind of analysis?
> /load data-analyst.worker
[Loaded data-analyst worker with tools: pandas_query, plot_chart]
> Here's my CSV...
[Tool call: pandas_query("df.describe()")]
```
Worker loaded on-demand, tools now available.

### Scenario 6: Pre-approved tools in worker config
```yaml
# data-analyst.worker
toolsets:
  pandas:
    _approval_config:
      pandas_query:
        pre_approved: true  # Safe, read-only
      pandas_write:
        pre_approved: false  # Needs approval
```
Some tools pre-approved based on worker author's judgment.

### Scenario 7: Approval in nested delegation
```
orchestrator -> researcher -> shell.run("curl ...")
```
Who approves the shell command?
- Option A: Bubble to user always (safe but noisy)
- Option B: Trust chain - if orchestrator is trusted, its delegates inherit trust
- Option C: Configurable per-worker trust boundaries

### Scenario 8: Headless mode, read-only tools only
```
$ llm-do --headless "Summarize docs in ./papers"
[Tool call: filesystem.list_files("./papers")]
[Tool call: filesystem.read_file("paper1.pdf")]
```
Tooling should be constrained to preapproved reads. Writes and network fetch
should be hidden or blocked in this mode.

### Scenario 9: Research session with sources panel
```
$ llm-do researcher.worker
> Find 5 recent papers on topic X and summarize key methods
[Tool call: web_search("topic X")]
[Sources panel: 5 papers, each with title + link + year]
```
UI can show a "sources" panel and require approvals for any new fetches.

### Scenario 10: Analyst run with structured output
```
$ llm-do --headless analyst.worker "Summarize ACME Q2 results" --format json
{"company": "...", "kpis": [{"name": "revenue", "value": "...", "source": "..."}]}
```
Output needs to be machine-readable and include provenance for each field.

---

## `/load` Slash Command Design

### When would `/load` be useful?

**Story A: Gradual capability discovery**
```
$ llm-do
> How do I parse JSON in Python?
[explains json.loads()]
> Actually, can you help me write a script?
> /load coding.worker
[Now has file tools, can write code]
```
User starts simple, realizes they need more.

**Story B: Task switching mid-session**
```
$ llm-do coding.worker
> [finishes coding task]
> Now I need to research best practices for this pattern
> /load researcher.worker
[Switches to research mode]
```
Different phase of work needs different tools.

**Story C: Debugging/testing workers**
```
$ llm-do
> /load my-new.worker
[Tests worker]
> /reload
[Reloads after editing worker file]
```
Rapid iteration during development.

### How should `/load` work?

#### Option A: Replace current agent
```
> /load researcher.worker
[History cleared, new worker takes over]
```
- **Pros:** Simple mental model, clean slate
- **Cons:** Loses conversation context
- **Use case:** Task switching, starting fresh

#### Option B: Replace but keep history
```
> /load researcher.worker
[New worker, but sees previous messages as context]
```
- **Pros:** Continuity, new worker understands what was discussed
- **Cons:** Old messages may confuse new worker (different tools/persona)
- **Use case:** Handoff scenarios

#### Option C: Sub-agent delegation
```
> /load researcher.worker "find sources on topic X"
[Spawns researcher as sub-agent, returns results to parent]
[Parent continues with results]
```
- **Pros:** Preserves full context, composable
- **Cons:** More complex, parent needs to be a worker too
- **Use case:** Orchestration, complex multi-phase tasks
- **Similar to:** Claude Code's Task tool

#### Option D: Add tools incrementally
```
> /load pandas_tools.py
[Current worker gains new tools, stays same otherwise]
```
- **Pros:** Minimal disruption, just adds capability
- **Cons:** Only works for tool files, not full workers
- **Use case:** "I need one more tool"

### Recommended approach: Context-aware `/load`

| Command | Behavior |
|---------|----------|
| `/load worker.worker` | Replace current agent, offer choice to keep/clear history |
| `/load worker.worker "task"` | Delegate to sub-agent, return results (requires current worker) |
| `/load tools.py` | Add tools to current session |
| `/reload` | Reload current worker (for development) |
| `/unload tools.py` | Remove tools from session |

### Key questions for `/load`:

1. **What happens to pending approvals?** Clear them on worker switch?

2. **Can you `/load` if you started with no worker?**
   - Yes: bare chat → worker chat
   - The "worker" becomes the loaded one

3. **What about incompatible tool contexts?**
   - Worker A has shell sandbox in /tmp
   - Worker B expects different working directory
   - Need to handle context conflicts

4. **History format compatibility?**
   - Worker A's tool calls in history
   - Worker B doesn't have those tools
   - LLM may be confused by unfamiliar tool results

---

## Affordances by Work Type

**Programming / engineering**
- Fast iteration (reload worker, rerun prompt, quick diff of changes)
- Clear tool provenance (show exact commands, file edits, and failures)
- Tight feedback loops (shortcuts for tests/linters, verbose tool logs on demand)
- Safe automation (headless mode with predictable approvals and deterministic output)

**Research / literature review**
- Source tracking (citations, metadata, and saved source lists)
- Search and ingest workflows (bulk import PDFs, dedupe, tag, summarize)
- Evidence-first summaries (claims linked to specific sources)
- Exportable notes (Markdown/JSON with citations for paper drafts)

**Investor analysis / due diligence**
- Structured extraction (tables/CSV/JSON output for KPIs and comparisons)
- Auditability (every number tied to a source and timestamp)
- Assumption tracking (explicit caveats and confidence levels)
- Reproducibility (repeatable runs with stable prompts and tool logs)

**General knowledge work**
- Low-friction entry (chat-first, minimal flags needed)
- Gradual capability discovery (load tools when needed)
- Safe defaults (clear approval prompts, conservative tool exposure)

---

## UI Choices to Support Affordances

- **Status indicators:** active worker, model, approval mode, and tool exposure policy
- **Tool visibility:** show/hide tools based on headless policy; explain why tools are unavailable
- **Source panel:** list documents, citations, and downloads with quick preview
- **Output modes:** plain text vs Markdown vs JSON/CSV; keep it explicit per run
- **Approval ergonomics:** session-level allow, scoped allow (directory/tool), and clear risk text
- **History controls:** keep/clear history on worker switch; show which tools were active

---

## Open Design Questions

1. **Default mode** - Should `llm-do` alone start chat? What if there's a prompt on CLI?
   - `llm-do` → chat
   - `llm-do "prompt"` → chat with initial prompt? or headless single-turn?

2. **Worker discovery** - How to find workers without explicit paths?
   - `llm-do.yaml` in project root?
   - `~/.config/llm-do/workers/` for global workers?
   - Auto-scan current directory?

3. **Headless tool exposure** - Should headless runs only advertise tools that
   are guaranteed to succeed without approvals?

4. **Structured output defaults** - Should certain workers declare a preferred
   output format (Markdown/JSON) to reduce ambiguity?

3. **Trust boundaries** - How deep does approval go in nested workers?

4. **Hot reload** - File watcher for worker changes during development?

5. **`/load` semantics** - Replace vs delegate vs augment?
