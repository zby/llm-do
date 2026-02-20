# What doesn't work

Honest assessment of friction encountered in the arscontexta knowledge system.

## Too many skills

16 local skills + 10 plugin commands. Most are rarely used. The cognitive overhead of knowing what's available exceeds the value of having specialized commands. A few general-purpose operations (extract, connect, review) cover 90% of real work.

## Queue and pipeline machinery

The processing queue (`queue.json`), task management, and multi-phase pipeline add overhead that exceeds their value at this project's scale. Simple "just do it" beats "add to queue, process later, track state" for a project with one active contributor.

## Schema validation as a separate step

Creating a validation phase with FAIL/WARN/PASS reporting creates compliance burden without proportional benefit. Better to have good templates that guide correct structure at creation time (see: template fields as behavioral nudges in what-works.md).

## Session rhythm protocol

The prescribed orient → work → persist cycle is too rigid. Agents naturally orient themselves when context is good (CLAUDE.md, recent files) and naturally persist when they have something worth saving. The protocol adds ceremony without changing behavior.

## Connection requirements outpace connection-making

The system generated requirements for connections (orphan detection, dangling link checks, index membership rules) faster than connections were actually made. At one point the orphan rate was ~90%. Rules about linking are less effective than making linking easy and natural.
