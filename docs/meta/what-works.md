# What works

Patterns that have proven valuable in practice.

## Prose-as-title convention

Note titles that work as claims when linked make the graph self-documenting. "Since [[thin adapters reduce coupling between providers and runtime]]" reads as prose and tells you what the note argues without opening it. Titles-as-labels ("adapter notes", "runtime thoughts") destroy this property.

## Template fields as behavioral nudges

The `areas: []` field in note templates guides agents to update indexes without explicit rules. The agent fills in the template, hits the empty array, and naturally asks "which index does this belong to?" The CLAUDE.md rule reinforces this, but the template is what makes it automatic. See [the observation](observations/template-areas-field-nudges-index-updates.md) that triggered this directory.

## Discovery-first as creation constraint

Checking findability *before* saving prevents orphan accumulation. Four questions: Does the title work as a claim? Does the description add information beyond the title? Is this linked from at least one index? Can this be linked without dragging irrelevant context? If any answer is no, fix it before saving.

## Description as progressive disclosure

A one-sentence description in frontmatter lets you decide whether to read the full note without opening it. `rg '^description:.*runtime' docs/notes/` becomes a lightweight search over note summaries. The description field is the most important metadata a note can have.

## Public/internal boundary

Keeping knowledge system artifacts out of public docs (`docs/*.md`) prevents coupling. Public documentation has its own audience and conventions. Internal notes can evolve freely without worrying about external readers.

## Extract, connect, review cycle

A simple three-phase pipeline that works. Extract pulls insights from source material. Connect finds relationships to existing notes (the backward pass — updating older notes to reference newer ones). Review checks quality. The connect phase is where most value is created, because it's where isolated notes become a graph.

## Input classification before processing

External sources (papers, articles, blog posts) need different treatment than domain research or design explorations. Classifying input type before processing prevents applying the wrong extraction strategy — you don't decompose a design exploration into atomic claims the same way you would a research paper.
