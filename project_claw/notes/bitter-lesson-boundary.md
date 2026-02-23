---
description: The bitter lesson has a boundary — calculators vs vision features illustrate when exact solutions survive scaling and when they don't
type: note
traits: [has-claim]
areas: []
status: current
---

# The bitter lesson stops at calculators

The [bitter lesson](../sources/wikipedia-bitter-lesson.md) says general methods leveraging computation beat hand-crafted domain knowledge. But both calculators and hand-crafted vision features are narrow, domain-specific, human-engineered solutions. The bitter lesson predicts both should lose to general methods plus scale. Only one did.

## Two narrow solutions, opposite fates

**Vision features** (SIFT, Haar cascades, Canny edge detection) had mathematical formulations and provable properties — scale invariance, rotation invariance, formal optimality criteria. They looked like exact solutions. But learned representations demolished them. The bitter lesson won.

**Calculators** (arithmetic, sorting, cryptography) implement algorithms for formally specified problems. No amount of scaling makes a neural net more reliable at multiplying large numbers. The bitter lesson doesn't apply.

Both are narrow. Both are human-engineered. The difference isn't scope — it's whether the specification fully captures the problem.

## Specifications that are the problem vs. theories about the problem

The vision algorithms were exact solutions to the wrong specifications. "Detect edges" was a human theory of what seeing requires, not a definition of seeing itself. The algorithm perfectly met its spec, but the spec was an approximation of the real problem. Scale revealed this by showing that learned features, which never committed to a theory of seeing, worked better.

Arithmetic has no gap between spec and problem. The specification of multiplication IS multiplication. A calculator is practical because the problem is fully formalised — there is nothing left for a general method to discover.

## The boundary is real but blurry

Calculators are the easy case: we know exactly what we want, and we've known since the start. But most practical solutions don't arrive with that clarity. The transistor wasn't obviously practical. Neither was the Fourier transform, or public-key cryptography before the internet. Practicality emerged from composition, not from any single step. You can't use "is this obviously practical?" as a reliable test.

The vision researchers faced this problem. Each individual feature — edge detection, corner detection, scale-invariant keypoints — was genuinely useful in isolation. The failure was in composition: the pieces didn't add up to "seeing." But that failure was only visible in retrospect, after learned representations demonstrated a better path.

And even that verdict may not be final. The bitter lesson describes a trajectory, not a law of nature. Edge detection lost as a top-level approach to vision, but it might return as a component *inside* a learned system, speeding up some critical path. This already happens elsewhere: FlashAttention is hand-crafted algorithmic optimization inside learned architectures; tokenizers are engineered preprocessing that learned models depend on. Approaches that get bitter-pilled away at one level of the stack sometimes reappear embedded within the general method at another.

## Crystallisation and softening

[Crystallisation](./crystallisation-learning-timescales.md) fills the gap between training and in-context learning by encoding knowledge into repo artifacts — tests, specs, conventions — each at a different grade of verifiability. But every such artifact also encodes a decomposition of some larger problem. Some decompositions are calculators: the spec fully captures the subproblem, and the solution is correct by construction. Others are vision features: the spec is a plausible human theory that scale may eventually outperform. Since you can't reliably tell which regime you're in until scale tests the distinction, practical systems will always be hybrids — part crystallised, part learned.

This means crystallisation has a complement: **softening**. Where crystallisation hardens a working solution into an exact artifact, softening replaces a crystallised component with a learned or general-purpose one when scale makes that viable. Edge detection was crystallised (hand-coded algorithms), softened (replaced by learned features), and may re-crystallise at a different level of the stack (as an accelerator inside a learned architecture). The two processes run continuously.

Good practice in a hybrid system:

1. **Crystallise for current leverage, not permanence.** A test that checks "does this function return the right number" is probably a calculator. A convention that says "always decompose agents into these three phases" is probably a vision feature. Crystallise both — but expect the second kind to eventually soften.

2. **Prefer specs that describe what over how.** The more a crystallised artifact encodes a theory of how something works (rather than what it should produce), the more likely it is a softening candidate. "This endpoint returns X given Y" survives longer than "always process requests in three stages."

3. **Watch for composition failure as a softening signal.** The vision features each worked in isolation. The signal that the spec was wrong came when they failed to compose into the larger capability. If crystallised conventions don't compose into better systems, that's the signal to soften — replace the rigid decomposition with a learned one.
