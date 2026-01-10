# Recursive Problem Patterns for LLM Workers

> **TL;DR**: See [recursive-patterns-summary.md](recursive-patterns-summary.md) for a condensed version with one representative example.

This document catalogs problems that benefit from recursive LLM worker architectures,
with concrete sketches of how to implement each using llm-do workers.

## Why Recursion Matters for LLMs

The key constraint when LLMs handle complex tasks is **context limits**:
- **Hard limits**: Token limits that cause truncation or failure
- **Soft limits**: LLMs become more distracted and erratic with longer contexts

Recursion addresses this by:
1. Breaking work into manageable chunks that fit comfortably in context
2. Each recursive call gets a fresh context (messages are locals)
3. Parent only sees the result, not the full child conversation
4. Enables arbitrarily deep processing while staying within context bounds

---

## Problem Catalog

### 1. Document Summarization (Hierarchical Reduction)

**Problem**: Summarize a very long document (e.g., 500-page book, legal corpus).

**Why recursion**: Document exceeds context. Even if it fits, quality degrades.

**Pattern**: Map-reduce summarization tree
- Chunk document into digestible pieces
- Summarize each chunk
- Recursively summarize the summaries until one remains

```yaml
# summarizer.worker
---
name: summarizer
description: Recursively summarize text, handling documents of any length
model: anthropic:claude-haiku-4-5
toolsets:
  - summarizer  # Self-reference for recursion
---
You are a document summarizer.

Given TEXT:
1. If TEXT is short enough (under 2000 words), summarize it directly in 200-400 words
2. If TEXT is too long:
   a. Split into 3-5 roughly equal chunks
   b. Call summarizer(input=chunk) for each chunk
   c. Combine the returned summaries
   d. If combined summaries are still too long, call summarizer on the combined result
   e. Return the final summary

Always preserve key facts, figures, and the document's main argument.
```

**Execution trace**:
```
summarizer("500 page document")
  ├── summarizer(chunk_1)  → summary_1
  ├── summarizer(chunk_2)  → summary_2
  ├── summarizer(chunk_3)  → summary_3
  └── summarizer(combined summaries)
        └── final summary (fits in one call)
```

---

### 2. Task Decomposition / Planning

**Problem**: Plan how to accomplish a complex goal (e.g., "build a web app", "write a research paper").

**Why recursion**: Complex tasks decompose into subtasks, which may themselves need decomposition.

**Pattern**: Recursive decomposition until tasks are atomic

```yaml
# planner.worker
---
name: planner
description: Decompose complex tasks into actionable plans
model: anthropic:claude-haiku-4-5
schema_out_ref: schemas.py:Plan
toolsets:
  - planner  # Self-reference for subtask decomposition
---
You are a task planner.

Given a GOAL, create a plan:
1. If GOAL is simple (can be done in one focused session), return it as an atomic task
2. If GOAL is complex:
   a. Identify 2-5 major subtasks that together achieve GOAL
   b. For each subtask that seems non-trivial, call planner(input=subtask) to decompose it
   c. Assemble the full plan tree

Output format: structured Plan with tasks and their subtasks.

Criteria for "atomic":
- Takes less than 30 minutes for an expert
- Has clear success criteria
- Doesn't require major context switches
```

**Schema**:
```python
# schemas.py
class Task(BaseModel):
    description: str
    is_atomic: bool
    subtasks: list["Task"] = []
    success_criteria: str

class Plan(BaseModel):
    goal: str
    root_task: Task
```

---

### 3. Code Analysis and Refactoring

**Problem**: Analyze a large codebase for patterns, bugs, or refactoring opportunities.

**Why recursion**: Codebases are hierarchical (repo → packages → modules → classes → methods).

**Pattern**: Traverse code structure recursively, aggregating findings

```yaml
# code_analyzer.worker
---
name: code_analyzer
description: Recursively analyze code structure and quality
model: anthropic:claude-haiku-4-5
toolsets:
  - code_analyzer  # Self-reference for subdirectory/submodule analysis
  - filesystem_readonly
---
You analyze code quality and structure.

Given a PATH (file or directory):

If PATH is a file:
  - Analyze: complexity, potential bugs, style issues, test coverage
  - Return findings for this file

If PATH is a directory:
  - List contents
  - For each significant subdirectory or file:
    - Call code_analyzer(input=subpath, attachments=[])
  - Aggregate findings from all children
  - Add any directory-level observations (architecture, organization)
  - Return combined analysis

Prioritize high-impact findings. Skip generated code, vendor directories, etc.
```

---

### 4. Mathematical/Logical Proof

**Problem**: Prove a theorem or verify a complex logical argument.

**Why recursion**: Proofs naturally decompose into lemmas.

**Pattern**: Prove by reducing to subproofs

```yaml
# prover.worker
---
name: prover
description: Construct and verify logical proofs
model: anthropic:claude-sonnet-4-5  # Needs stronger reasoning
toolsets:
  - prover  # Self-reference for subproofs/lemmas
---
You are a proof assistant.

Given a STATEMENT to prove and available AXIOMS/ASSUMPTIONS:

1. If STATEMENT follows directly from axioms in 1-2 steps, write the direct proof
2. If STATEMENT is complex:
   a. Identify useful lemmas that would help prove STATEMENT
   b. For each lemma, call prover(input=lemma) to verify it
   c. Use verified lemmas to construct the final proof
3. If STATEMENT appears false, construct a counterexample

Always verify each step. Never assume unproven statements.
```

---

### 5. Research Question Exploration

**Problem**: Answer a complex research question requiring multi-source synthesis.

**Why recursion**: Questions spawn sub-questions; answers require integration.

**Pattern**: Question → sub-questions → answers → synthesis

```yaml
# researcher.worker
---
name: researcher
description: Research complex questions by decomposition
model: anthropic:claude-haiku-4-5
toolsets:
  - researcher  # Self-reference for sub-question investigation
server_side_tools:
  - tool_type: web_search
    max_uses: 20
---
You are a research assistant.

Given a QUESTION:

1. If QUESTION is factual and answerable directly, search and answer it
2. If QUESTION is complex/multi-faceted:
   a. Decompose into 2-4 sub-questions
   b. Call researcher(input=sub_question) for each
   c. Synthesize sub-answers into a coherent response
   d. Identify any contradictions or gaps
   e. Return the synthesized answer with confidence assessment

Cite sources. Flag uncertainty. Distinguish fact from inference.
```

---

### 6. Debate/Adversarial Analysis

**Problem**: Thoroughly analyze an argument by considering counterarguments.

**Why recursion**: Counterarguments have counter-counterarguments; depth reveals strength.

**Pattern**: Argument → counterarguments → rebuttals → evaluation

```yaml
# debate_analyzer.worker
---
name: debate_analyzer
description: Analyze arguments through recursive adversarial examination
model: anthropic:claude-haiku-4-5
schema_out_ref: schemas.py:ArgumentAnalysis
toolsets:
  - debate_analyzer  # Self-reference for analyzing counterarguments
---
You analyze arguments through adversarial reasoning.

Given an ARGUMENT and DEPTH (default 2):

1. Identify the argument's key claims and assumptions
2. Generate strongest counterarguments (steel-man opponents)
3. If DEPTH > 0:
   a. For each significant counterargument, call:
      debate_analyzer(input=counterargument, depth=DEPTH-1)
   b. This produces analysis of rebuttals to counterarguments
4. Synthesize: which points survive scrutiny? What's the refined conclusion?

Maintain intellectual honesty. The goal is truth, not winning.
```

**Schema**:
```python
class ArgumentAnalysis(BaseModel):
    original_claim: str
    strengths: list[str]
    counterarguments: list["CounterargumentAnalysis"]
    refined_conclusion: str
    confidence: float

class CounterargumentAnalysis(BaseModel):
    counterargument: str
    rebuttals: list[str]
    survives_scrutiny: bool
```

---

### 7. Creative Writing (Hierarchical Expansion)

**Problem**: Write a long-form creative piece (novel, screenplay, game narrative).

**Why recursion**: Outline → chapters → scenes → paragraphs.

**Pattern**: Recursive expansion from outline to prose

```yaml
# writer.worker
---
name: writer
description: Recursively expand outlines into full prose
model: anthropic:claude-haiku-4-5
toolsets:
  - writer  # Self-reference for expanding subsections
---
You are a creative writer.

Given CONTENT and TARGET_LENGTH:

1. If TARGET_LENGTH is small (under 500 words), write the prose directly
2. If TARGET_LENGTH is large:
   a. Create a structural outline (chapters, scenes, beats)
   b. Allocate word counts to each section
   c. For each section, call writer(content=section_prompt, target_length=allocated)
   d. Assemble sections with transitions

Maintain consistent:
- Voice and tone
- Character voices
- Plot continuity
- Pacing
```

---

### 8. Data Pipeline Construction

**Problem**: Transform complex, nested data structures.

**Why recursion**: Data is often hierarchical (JSON, XML, nested objects).

**Pattern**: Process nodes, recursing into children

```yaml
# data_transformer.worker
---
name: data_transformer
description: Transform complex nested data structures
model: anthropic:claude-haiku-4-5
toolsets:
  - data_transformer  # Self-reference for nested structures
---
You transform data structures.

Given SOURCE_DATA and TRANSFORMATION_RULES:

1. If SOURCE_DATA is a primitive or simple object, apply rules directly
2. If SOURCE_DATA is complex/nested:
   a. Apply top-level transformations
   b. For each nested structure that needs transformation:
      - Call data_transformer(source_data=nested, rules=applicable_rules)
   c. Reassemble with transformed children

Handle: renaming, restructuring, filtering, type conversion, validation.
```

---

### 9. Test Generation

**Problem**: Generate comprehensive tests for a codebase.

**Why recursion**: Test module → test classes → test methods → test cases.

**Pattern**: Hierarchical test generation matching code structure

```yaml
# test_generator.worker
---
name: test_generator
description: Generate comprehensive tests recursively
model: anthropic:claude-haiku-4-5
toolsets:
  - test_generator  # Self-reference for nested test generation
  - filesystem_readonly
---
You generate tests.

Given CODE_PATH:

1. If CODE_PATH is a single function/method:
   - Generate test cases covering: happy path, edge cases, error conditions
   - Return test code

2. If CODE_PATH is a class:
   - Generate test class skeleton
   - For each method, call test_generator(code_path=method)
   - Assemble into complete test class

3. If CODE_PATH is a module/package:
   - Create test module structure
   - For each significant component, call test_generator(code_path=component)
   - Assemble into test suite
```

---

### 10. Knowledge Graph Construction

**Problem**: Build a knowledge graph from unstructured text.

**Why recursion**: Entities reference other entities; relationships form graphs.

**Pattern**: Extract → resolve references → merge → recurse on references

```yaml
# kg_builder.worker
---
name: kg_builder
description: Build knowledge graphs from text recursively
model: anthropic:claude-haiku-4-5
schema_out_ref: schemas.py:KnowledgeFragment
toolsets:
  - kg_builder  # Self-reference for expanding entity references
server_side_tools:
  - tool_type: web_search
    max_uses: 10
---
You build knowledge graphs.

Given TEXT and DEPTH (default 2):

1. Extract entities and relationships from TEXT
2. If DEPTH > 0:
   a. For each entity that needs expansion (referenced but not detailed):
      - Search for more information
      - Call kg_builder(text=entity_info, depth=DEPTH-1)
   b. Merge results into growing graph
3. Return knowledge fragment with entities, relationships, and references

Deduplicate entities. Resolve coreferences. Note confidence levels.
```

---

### 11. Bug Root Cause Analysis

**Problem**: Find the root cause of a bug in a complex system.

**Why recursion**: Symptoms → proximate causes → deeper causes → root cause.

**Pattern**: Follow causal chain recursively

```yaml
# bug_analyzer.worker
---
name: bug_analyzer
description: Trace bugs to root causes recursively
model: anthropic:claude-haiku-4-5
toolsets:
  - bug_analyzer  # Self-reference for analyzing deeper causes
  - filesystem_readonly
  - shell_readonly
---
You analyze bugs to find root causes.

Given BUG_DESCRIPTION and EVIDENCE:

1. Analyze immediate symptoms and form hypotheses
2. For each hypothesis:
   a. Identify what code/data could cause this
   b. If cause is another bug/issue, call bug_analyzer(bug_description=cause)
   c. Continue until reaching: config error, logic flaw, external dependency, or design issue
3. Report the causal chain from root cause to symptom
4. Suggest fixes at appropriate levels

Don't just find what's wrong—find WHY it's wrong.
```

---

### 12. Multi-level Translation/Localization

**Problem**: Translate and culturally adapt content across languages.

**Why recursion**: Document → sections → sentences, with context preservation.

**Pattern**: Hierarchical translation with context passing

```yaml
# translator.worker
---
name: translator
description: Translate with cultural adaptation recursively
model: anthropic:claude-haiku-4-5
toolsets:
  - translator  # Self-reference for section translation
---
You translate and localize content.

Given CONTENT, SOURCE_LANG, TARGET_LANG, and CONTEXT:

1. If CONTENT is short (under 500 words):
   - Translate directly with cultural adaptation
   - Preserve: tone, intent, idioms (adapted), humor (adapted)

2. If CONTENT is long:
   a. Extract document-level context (domain, audience, style)
   b. Split into logical sections
   c. For each section, call translator(content=section, context=doc_context)
   d. Ensure consistency: terminology, tone, references
   e. Assemble final translation

Track: terms requiring consistency, cultural adaptations made, uncertain translations.
```

---

### 13. Game AI / Decision Trees

**Problem**: Make optimal decisions in game-like scenarios (minimax, planning).

**Why recursion**: Game trees are naturally recursive (my move → opponent's move → ...).

**Pattern**: Recursive game tree exploration

```yaml
# game_ai.worker
---
name: game_ai
description: Explore game trees for optimal decisions
model: anthropic:claude-haiku-4-5
schema_out_ref: schemas.py:GameAnalysis
toolsets:
  - game_ai  # Self-reference for exploring future states
---
You analyze game positions and recommend moves.

Given GAME_STATE and DEPTH (default 3):

1. If DEPTH == 0 or game is over:
   - Return static evaluation of position

2. If DEPTH > 0:
   a. Generate all legal moves
   b. For each promising move (prune obviously bad ones):
      - Call game_ai(game_state=result_of_move, depth=DEPTH-1)
   c. Apply minimax: maximize our score, assume opponent minimizes
   d. Return best move and expected value

Consider: material, position, tempo, threats, long-term structure.
```

---

### 14. Explanation Generation (Multi-level)

**Problem**: Explain a concept at multiple levels of abstraction.

**Why recursion**: Explanations reference concepts that may themselves need explanation.

**Pattern**: Explain → identify sub-concepts → explain those → link

```yaml
# explainer.worker
---
name: explainer
description: Generate multi-level explanations recursively
model: anthropic:claude-haiku-4-5
toolsets:
  - explainer  # Self-reference for explaining sub-concepts
---
You generate explanations at appropriate depth.

Given CONCEPT, AUDIENCE_LEVEL, and MAX_DEPTH:

1. Explain CONCEPT at AUDIENCE_LEVEL
2. Identify prerequisite concepts the audience might not know
3. If MAX_DEPTH > 0 and there are unknown prerequisites:
   a. For each prerequisite, call explainer(concept=prereq, max_depth=MAX_DEPTH-1)
   b. Link prerequisite explanations appropriately
4. Return layered explanation with clear navigation

Don't over-explain. Match audience level. Use analogies for complex concepts.
```

---

### 15. Contract/Legal Analysis

**Problem**: Analyze complex legal documents for risks and obligations.

**Why recursion**: Contracts reference other documents, definitions, and clauses.

**Pattern**: Analyze document → follow references → aggregate findings

```yaml
# contract_analyzer.worker
---
name: contract_analyzer
description: Analyze legal documents recursively
model: anthropic:claude-haiku-4-5
toolsets:
  - contract_analyzer  # Self-reference for referenced documents
  - filesystem_readonly
---
You analyze legal documents.

Given DOCUMENT:

1. Identify document type and structure
2. Extract key terms, obligations, rights, and conditions
3. For each reference to external documents or defined terms:
   a. If definition is elsewhere in corpus, call contract_analyzer(document=reference)
   b. Integrate referenced analysis
4. Flag: unusual clauses, risks, missing protections, ambiguities
5. Generate summary with risk assessment

Precision matters. Distinguish SHALL from SHOULD from MAY. Note jurisdictional assumptions.
```

---

## Implementation Patterns

### Pattern A: Self-Recursive Worker

Worker includes itself in toolsets. Simple but requires policy change.

```yaml
toolsets:
  - self_name  # Requires enabling self-recursion
```

### Pattern B: Twin Workers

Two workers that call each other. Works with current architecture.

```yaml
# decomposer_a.worker
toolsets:
  - decomposer_b

# decomposer_b.worker
toolsets:
  - decomposer_a
```

Identical instructions, just different names. Alternates between them.

### Pattern C: Typed Recursion

Different workers for different levels of the hierarchy.

```yaml
# document_analyzer.worker
toolsets:
  - section_analyzer

# section_analyzer.worker
toolsets:
  - paragraph_analyzer

# paragraph_analyzer.worker
toolsets: []  # Base case
```

### Pattern D: Depth-Controlled Recursion

Pass explicit depth parameter, decrement on each call.

```yaml
# recursive_analyzer.worker
schema_in_ref: schemas.py:RecursiveInput

# schemas.py
class RecursiveInput(BaseModel):
    data: str
    depth: int = 3
```

Worker checks depth, only recurses if depth > 0.

---

## Depth Limit Considerations

The default max_depth of 5 is usually sufficient because:

1. **Exponential work**: Each level multiplies work. Depth 5 with branching factor 3 = 243 calls
2. **Quality focus**: Deeper isn't always better; focus matters more
3. **Token efficiency**: Each call has overhead; deep recursion wastes tokens
4. **Natural limits**: Most problems have natural depth (chapters → sections → paragraphs)

For problems needing deeper recursion:
- Increase max_depth via config
- Use iterative deepening
- Checkpoint and resume

---

## Context Management

Key insight: **messages are locals, not globals**.

Each worker call gets fresh context containing only:
- The worker's instructions
- The input to this call
- Tool calls/results from this call's execution

Parent never sees child's full conversation—only the final result.

This means:
- Recursion doesn't accumulate context infinitely
- Each level works within comfortable token budget
- Information flows explicitly through inputs and outputs
- No hidden state leakage between calls

---

## Next Steps

1. **Enable self-recursion**: Remove `k != name` filter in registry.py:174
2. **Add recursion examples**: Demonstrate 2-3 patterns from this doc
3. **Depth monitoring**: Add telemetry for recursion depth usage
4. **Iterative deepening**: Support for incremental depth increase
5. **Checkpoint/resume**: Save state for very deep explorations
