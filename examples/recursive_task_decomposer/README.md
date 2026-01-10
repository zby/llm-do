# Recursive Task Decomposer Example

Demonstrates non-tail recursion by decomposing a complex task into subtasks,
recursively expanding the non-atomic ones, and merging results into a cohesive plan.

## Key Features

- **Non-tail recursion**: subtask calls return results that are merged into the final plan
- **Structured input**: task, context, and max depth are explicit
- **Bounded depth**: MAX_DEPTH controls recursion; runtime `--max-depth` is a safety cap

## Running

```bash
# From project root
llm-do examples/recursive_task_decomposer/main.worker --entry planner "$(cat examples/recursive_task_decomposer/sample_input.txt)"

# Or with max-depth control
llm-do examples/recursive_task_decomposer/main.worker --entry planner --max-depth 6 "$(cat examples/recursive_task_decomposer/sample_input.txt)"
```

## Sample Input

```
TASK: Plan a 2-day onboarding workshop for new backend engineers
CONTEXT: Remote team, 15 attendees, limited to 4 hours per day, include a hands-on lab
MAX_DEPTH: 2
```

## Expected Behavior

1. Break the workshop into agenda design, logistics, and lab preparation.
2. Recursively expand non-atomic subtasks (e.g., lab design) with MAX_DEPTH-1.
3. Merge returned subtasks into a numbered plan with success criteria.
