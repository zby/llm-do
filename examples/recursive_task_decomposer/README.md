# Recursive Task Decomposer Example

Demonstrates non-tail recursion by decomposing a complex task into subtasks,
recursively expanding the non-atomic ones, and merging results into a cohesive plan.

## Key Features

- **Non-tail recursion**: subtask calls return results that are merged into the final plan
- **Structured input**: task, context, and remaining depth are explicit
- **Bounded depth**: MAX_DEPTH caps recursion; runtime `--max-depth` is a safety cap

## Running

```bash
llm-do examples/recursive_task_decomposer/project.json
```

The manifest configures `max_depth: 10` and includes a default input for the sample task.

## Sample Input

```
TASK: Plan a 2-day onboarding workshop for new backend engineers
CONTEXT: Remote team, 15 attendees, limited to 4 hours per day, include a hands-on lab
REMAINING_DEPTH: 2
```

Notes:
- REMAINING_DEPTH values <0 are treated as 0.

## Expected Behavior

1. Break the workshop into agenda design, logistics, and lab preparation.
2. Recursively expand non-atomic subtasks while remaining depth > 0.
3. Merge returned subtasks into a numbered plan with success criteria within the (REMAINING_DEPTH + 1) * 4 line budget.
4. Never call the planner on the original task; only call it on specific subtasks.
