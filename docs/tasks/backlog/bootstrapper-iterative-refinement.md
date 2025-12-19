# Bootstrapper Iterative Refinement

## Idea

Enable the bootstrapper to automatically refine created workers based on output quality: create worker → run → evaluate → refine.

## Why

- Created workers are often imperfect on first attempt
- Manual iteration is tedious
- LLMs can self-correct given feedback

## Rough Scope

- Define evaluation criteria (how to measure worker output quality)
- Implement feedback loop: run worker, evaluate output, propose refinements
- Add iteration limit to prevent infinite loops
- Consider user approval checkpoints vs fully autonomous refinement

## Why Not Now

The bootstrapper is already experimental/"YOLO territory". Adding iterative refinement increases complexity and autonomy. Need more real-world usage of basic bootstrapper first.

## Trigger to Activate

Frequent manual refinement of bootstrapper-created workers suggests automation would pay off.
