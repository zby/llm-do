# Whiteboard → Project Plan Example

This example demonstrates how to use `llm-do` to turn photos of whiteboards into structured project plans using a vision-capable LLM.

It uses two workers:
1. **`whiteboard_planner`**: A vision+reasoning worker that looks at a single image and produces a markdown plan.
2. **`whiteboard_orchestrator`**: An orchestrator that finds all images in `input/`, delegates them to the planner, and saves the results to `plans/`.

## Setup

1.  **Enter the example directory**:
    ```bash
    cd examples/whiteboard_planner
    ```

2.  **Add your whiteboard photos**:
    Copy your `.jpg` or `.png` files into the `input/` directory.
    ```bash
    cp ~/Downloads/my_whiteboard_session.jpg input/
    ```

## Usage

Run the orchestrator. You must use a model that supports vision (like Claude 3.5 Sonnet, GPT-4o, or Gemini 1.5 Pro).

```bash
llm-do whiteboard_orchestrator \
  --model anthropic:claude-3-5-sonnet-latest \
  --approve-all
```

## Output

The generated project plans will be saved in the `plans/` directory as markdown files.

```bash
ls -l plans/
cat plans/my_whiteboard_session.md
```

## How it works

- The **Orchestrator** uses `list_files` to find files.
- It iterates through them and calls `whiteboard_planner` to invoke the **Planner**.
- The **Planner** receives the image as an attachment.
- The **Planner** uses a detailed **Rubric** (`workers/RUBRIC.md`) to interpret the board.
- The **Orchestrator** takes the result and uses `write_file` to save it.
