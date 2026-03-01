---
description: Index of notes about how systems learn, verify, and improve — Simon's capacity framework, stabilisation/crystallisation/distillation mechanisms, oracle theory
type: index
status: current
---

# Learning theory

How systems learn, verify, and improve. These notes define learning mechanisms, verification gradients, and their application to agentic systems.

## Foundations

- [interpreting fuzzy specifications](../../docs/theory.md) — LLM-based systems have two distinct properties: execution indeterminism and semantic fuzziness; the "program sampling" model, interpretation space narrowing, semantic boundaries, and the stabilise/soften cycle

## Definitions

- [learning-is-capacity-change](./learning-is-capacity-change.md) — Simon's framework: learning is any change in a system's capacity to adapt; capacity decomposes into generality vs a reliability/speed/cost compound, and three mechanisms operate on that trade-off differently
- [agentic-systems-learn-through-three-distinct-mechanisms](./agentic-systems-learn-through-three-distinct-mechanisms.md) — the three mechanisms named: stabilisation narrows distribution, crystallisation transitions medium, distillation extracts procedures — all are capacity change per Simon but differ in what changes

## Mechanisms

- [stabilisation](./stabilisation.md) — definition: narrowing the output distribution, trading generality for reliability/speed/cost without changing medium
- [crystallisation](./crystallisation.md) — definition: phase transition from natural language to executable code, changing medium, consumer, and verification regime
- [distillation](./distillation.md) — definition: extracting operational procedures from discursive reasoning, staying in the same medium but changing rhetorical mode
- [deploy-time-learning-the-missing-middle](./deploy-time-learning-the-missing-middle.md) — repo artifacts fill the gap between training and in-context learning; the three mechanisms provide a verifiability gradient from prompt tweaks to deterministic code
- [continuous-learning-is-stabilisation-during-deployment](./continuous-learning-is-stabilisation-during-deployment.md) — AI labs' continuous learning is achievable through stabilisation with versioned artifacts, which beats weight updates on inspectability and rollback
- [storing-llm-outputs-is-stabilization](./storing-llm-outputs-is-stabilization.md) — choosing to keep an LLM output collapses a distribution to a point — stabilisation applied to artifacts
- [spec-mining-as-crystallisation](./spec-mining-as-crystallisation.md) — the operational mechanism: observe behavior, extract patterns, write deterministic code
- [softening-signals](./softening-signals.md) — testable indicators for where a component sits on the oracle spectrum

## Oracle & Verification

- [oracle-strength-spectrum](./oracle-strength-spectrum.md) — oracle strength (how cheaply and reliably you can verify correctness) determines where a component sits on the automation gradient
- [bitter-lesson-boundary](./bitter-lesson-boundary.md) — the boundary where exact solutions survive scaling vs where they don't — calculators vs vision features
- [error-correction-works-above-chance-oracles-with-decorrelated-checks](./error-correction-works-above-chance-oracles-with-decorrelated-checks.md) — error correction is viable when the oracle has discriminative power (TPR > FPR) and checks are decorrelated
- [reliability-dimensions-map-to-oracle-hardening-stages](./reliability-dimensions-map-to-oracle-hardening-stages.md) — Rabanser et al.'s four reliability dimensions each harden a different oracle question

## Applications

- [unified-calling-conventions-enable-bidirectional-refactoring](./unified-calling-conventions-enable-bidirectional-refactoring.md) — when agents and tools share a calling convention, stabilisation and crystallisation become local operations
- [programming-practices-apply-to-prompting](./programming-practices-apply-to-prompting.md) — typing, testing, progressive compilation, and version control transfer from programming to LLM prompting
- [ad-hoc-prompts-extend-the-system-without-schema-changes](./ad-hoc-prompts-extend-the-system-without-schema-changes.md) — the counterpoint: sometimes staying at the prompt level is the right choice
- [methodology-enforcement-is-stabilisation](./methodology-enforcement-is-stabilisation.md) — instructions, skills, hooks, and scripts form a stabilisation gradient for methodology
- [inspectable-substrate-not-supervision-defeats-the-blackbox-problem](./inspectable-substrate-not-supervision-defeats-the-blackbox-problem.md) — crystallisation counters the blackbox problem by choosing a substrate any agent can inspect, diff, test, and verify
- [instructions-are-typed-callables](./instructions-are-typed-callables.md) — skills should declare type signatures for composability and validation
