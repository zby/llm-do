---
description: Custom plain-text language for knowledge management with Tree-Sitter grammar, typed entities, 27 validation rules, and LSP. Makes the same programming-theory-over-psychology bet we do, but went further into formalization with a custom DSL.
type: note
status: current
areas: [related-systems]
last-checked: 2026-02-25
---

# Thalo

**Thought And Lore Language** — a structured plain-text format for personal knowledge management designed for AI collaboration. Inspired by plain-text accounting (Beancount, Ledger), it adapts that philosophy to knowledge bases.

**Repository:** https://github.com/rejot-dev/thalo
**Status:** Pre-1.0, actively maintained, well-engineered (monorepo, LSP, TypeScript)

## Core Ideas

**"Unit tests for knowledge."** The central claim is that knowledge bases and codebases are similar — both need good structure to compound, both decay without it. Thalo provides a validation feedback loop: AI generates entries, `thalo check` validates them against 27 rules, creating iterative refinement. This is strikingly close to our [oracle hardening](../oracle-strength-spectrum.md) — they're manufacturing hard oracles for knowledge quality.

**Grammar-based type system.** Entities define types of knowledge (e.g. `opinion`, `reference`, `lore`, `journal`) with typed metadata fields (`string`, `date`, `link`, literal unions like `"article" | "video"`) and required/optional content sections. Values are parsed into typed AST nodes by Tree-Sitter, not regex-validated. This is our [types mark affordances](../programming-language-types-applied-to-documents-mark-affordances.md) principle taken to its logical extreme — a full compiler rather than YAML frontmatter conventions.

**Plain text is paramount.** Pure text files in git, no database, no lock-in, works with any editor. Full scripting API. This aligns with our markdown-as-source-of-truth stance and the filesystem-over-databases pattern shared across all systems we track.

**Actualization abstraction.** Syntheses combine a query (what entries to pull) with a prompt (how to synthesize them). Running `thalo actualize` outputs sources + prompt as text — deliberately decoupled from any specific LLM. The knowledge specification is separate from the LLM invocation. This is a clean separation we don't currently have.

**Incremental everything.** Document edits apply incrementally (Tree-sitter edit API), semantic model updates incrementally, rules declare dependencies for targeted invalidation. The workspace is a live, incrementally-updated semantic model across files.

## The Shared Bet

Thalo is the system closest to our theoretical position. They explicitly argue that knowledge should be treated like code — with schemas, types, validation, version control. This is [programming practices applied to knowledge management](../programming-practices-apply-to-prompting.md) taken to its logical conclusion — where we apply typing, testing, and progressive compilation through conventions, they built an actual compiler. Their entity/entry system is our [document classification](../../claw-design/document-classification.md) with types and traits, but expressed as a formal grammar instead of YAML conventions.

The comparison illuminates a design spectrum:

| Dimension | Thalo | Claw |
|-----------|-------|------|
| Type system | Custom DSL, Tree-Sitter grammar | YAML frontmatter, convention-based |
| Validation | 27 compiler rules, deterministic | Skills + scripts, mix of deterministic and stochastic |
| Tooling | LSP, Prettier, VSCode extension | rg, skills, qmd |
| Format | Custom `.thalo` (embeddable in markdown) | Plain markdown |
| Schema evolution | `alter-entity` directive | Edit templates, update conventions |
| Link model | Typed links parsed by grammar | Markdown links with semantic context in prose |

## Key Divergences

**They built a language; we stayed in markdown.** The trade-off is clear: a custom grammar gives you compiler-grade validation, LSP, incremental parsing. But it also means a new syntax to learn, tooling to maintain, and knowledge locked into a format that only thalo tools can process. Our markdown approach is lower-ceremony, works with every tool that reads text, but validation is softer.

**Their validation is deterministic; ours is partly stochastic.** Their 27 rules are hard oracles — schema compliance, link resolution, type checking. Our quality checks mix hard oracles (frontmatter field presence, dangling links) with soft ones (description quality, connection genuineness). This maps to different positions on the [oracle strength spectrum](../oracle-strength-spectrum.md) — they've chosen to formalise more, accepting the cost of maintaining a grammar.

**They don't have a learning theory.** Thalo has validation (is this entry well-formed?) but no framework for deciding when to formalise something vs. leave it stochastic. No [crystallisation gradient](../crystallisation-learning-timescales.md), no stabilise/soften boundary. Their 27 rules are all fixed at design time — equivalent to jumping straight to the "script" level of the [methodology enforcement gradient](../../claw-design/methodology-enforcement-is-stabilisation.md), skipping the instruction and skill phases where practices prove out before hardening. Our type system [evolves through practice](../../claw-design/document-types-should-be-verifiable.md) — types crystallise from untyped notes as structure develops.

**No link semantics.** Their links are typed (the grammar knows `link` vs `link[]`) but don't carry relationship semantics. Our [link contracts](../../claw-design/link-contracts-framework.md) — extends, foundation, contradicts, enables — have no counterpart.

## What We Could Borrow

- **The "unit tests for knowledge" framing.** Resonates with oracle hardening but is more accessible language. Could be useful when explaining our approach.
- **Actualization as a pattern.** Separating "what to synthesize" (query) from "how to synthesize" (prompt) from "who synthesizes" (any LLM) is a clean decoupling we could apply to claw operations.
- **Incremental workspace model.** If we ever build tooling beyond rg + skills, their architecture (workspace → documents → incremental semantic analysis) is a good reference.

## What to Watch

- Do they develop schema evolution patterns (how types change over time) that inform our document classification evolution?
- Does the custom-language approach prove durable, or does maintenance burden push them toward simpler formats?
- How do they handle the boundary between what's formalised in the grammar and what stays free-form? This is their version of the crystallisation question.
- Does the validation feedback loop (AI generates → thalo checks → AI fixes) actually produce better knowledge over time? This would validate the shared programming-theory bet.

---

Relevant Notes:
- [oracle-strength-spectrum](../oracle-strength-spectrum.md) — foundation: Thalo's 27 rules are hard oracles manufactured for knowledge quality; the comparison illuminates what "oracle hardening" looks like when pursued to full formalization
- [programming-language-types-applied-to-documents-mark-affordances](../programming-language-types-applied-to-documents-mark-affordances.md) — foundation: Thalo's entity system is this principle taken to a full compiler; our YAML conventions occupy a different point on the same spectrum
- [programming-practices-apply-to-prompting](../programming-practices-apply-to-prompting.md) — synthesizes: Thalo is the most extreme example of programming practices (typing, testing, compilation) applied to knowledge management — they built an actual compiler where we use conventions
- [crystallisation-learning-timescales](../crystallisation-learning-timescales.md) — contrasts: Thalo has no crystallisation gradient; their rules are fixed at design time, while the verifiability gradient explains why progressive formalization (prompt -> schema -> code) beats upfront commitment
- [document-types-should-be-verifiable](../../claw-design/document-types-should-be-verifiable.md) — contrasts: our gradual typing approach (base types + traits, tolerance of misclassification) vs Thalo's grammar-enforced type system illustrates two solutions to the same problem — verifiable document structure
- [document-classification](../../claw-design/document-classification.md) — contrasts: our base types + traits model vs Thalo's entity definitions; same goal (structural contracts on knowledge), different mechanisms
- [methodology-enforcement-is-stabilisation](../../claw-design/methodology-enforcement-is-stabilisation.md) — contrasts: Thalo jumped straight to deterministic scripts; we maintain a gradient (instruction -> skill -> hook -> script) because not all methodology should complete the trajectory
- [link-contracts-framework](../../claw-design/link-contracts-framework.md) — gap: Thalo's typed links have no relationship semantics; our link contracts provide the semantic layer their grammar omits
- [Ars Contexta](./arscontexta.md) — sibling: both are compared against our theoretical position; arscontexta grounds in cognitive psychology where Thalo grounds in programming language theory, making them complementary reference points
- [files-not-database](../../claw-design/files-not-database.md) — convergence: Thalo's "plain text is paramount" independently validates the filesystem-over-databases pattern

Topics:
- [related-systems](./related-systems-index.md)
