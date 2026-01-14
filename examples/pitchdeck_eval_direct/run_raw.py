#!/usr/bin/env python
"""Pitch deck evaluation in raw Python (no llm-do tool plane).

Run with:
    uv run examples/pitchdeck_eval_direct/run_raw.py
    python examples/pitchdeck_eval_direct/run_raw.py
"""

import asyncio
import json
import mimetypes
from collections.abc import Sequence
from pathlib import Path

try:
    from slugify import slugify
except ImportError:
    raise ImportError("python-slugify required. Install with: pip install python-slugify")

from pydantic_ai import Agent
from pydantic_ai.messages import (
    BinaryContent,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserContent,
    UserPromptPart,
)

# =============================================================================
# CONFIGURATION
# =============================================================================

MODEL = "anthropic:claude-haiku-4-5"
# 0=quiet, 1=progress, 2=I/O details, 3=LLM messages
VERBOSITY = 1

# =============================================================================
# Paths
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.resolve()
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "evaluations"

def log(level: int, message: str) -> None:
    """Print when verbosity is high enough."""
    if VERBOSITY >= level:
        print(message)

def _format_tool_args(args: object) -> str:
    if isinstance(args, str):
        return args
    try:
        return json.dumps(args, sort_keys=True, default=str)
    except TypeError:
        return repr(args)


def _format_user_content(content: UserContent) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, BinaryContent):
        return f"<binary {len(content.data)} bytes {content.media_type}>"
    kind = getattr(content, "kind", None)
    if kind is not None:
        url = getattr(content, "url", None)
        if url is not None:
            return f"<{kind} {url}>"
        return f"<{kind}>"
    return repr(content)


def _format_user_prompt(content: str | Sequence[UserContent]) -> list[str]:
    if isinstance(content, str):
        return [content]
    return [_format_user_content(item) for item in content]


def log_llm_messages(messages: Sequence[object]) -> None:
    """Print model messages when verbosity is high enough."""
    if VERBOSITY < 3:
        return
    log(3, "LLM messages:")
    for message in messages:
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, UserPromptPart):
                    for line in _format_user_prompt(part.content):
                        log(3, f"  user: {line}")
                elif isinstance(part, ToolReturnPart):
                    log(3, f"  tool return {part.tool_name}: {part.content}")
                else:
                    log(3, f"  {part.__class__.__name__}: {part}")
        elif isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, TextPart):
                    log(3, f"  assistant: {part.content}")
                elif isinstance(part, ToolCallPart):
                    log(3, f"  assistant tool call {part.tool_name}: {_format_tool_args(part.args)}")
                else:
                    log(3, f"  {part.__class__.__name__}: {part}")
        else:
            log(3, f"  {message}")


def list_pitchdecks(input_dir: str = "input") -> list[dict]:
    """List pitch deck PDFs with pre-computed slugs and output paths."""
    input_path = PROJECT_ROOT / input_dir
    result = []
    if input_path.exists():
        for pdf in sorted(input_path.glob("*.pdf")):
            slug = slugify(pdf.stem)
            result.append({
                "file": str(pdf.resolve()),
                "slug": slug,
                "output_path": str((OUTPUT_DIR / f"{slug}.md").resolve()),
            })
    return result


def read_attachment(path: str) -> BinaryContent:
    """Read attachment data from disk and infer media type."""
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Attachment not found: {path}")

    size_bytes = file_path.stat().st_size
    media_type, _ = mimetypes.guess_type(str(file_path))
    if media_type is None:
        media_type = "application/octet-stream"

    log(2, f"Loaded attachment {file_path} ({size_bytes} bytes, {media_type})")
    return BinaryContent(data=file_path.read_bytes(), media_type=media_type)


def build_user_prompt(
    text: str, attachments: list[BinaryContent]
) -> str | list[UserContent]:
    """Build a multimodal prompt without llm-do runtime helpers."""
    if not attachments:
        return text if text.strip() else "(no input)"

    parts: list[UserContent] = [text if text.strip() else "(no input)"]
    parts.extend(attachments)
    return parts


async def evaluate_decks() -> str:
    """Run the evaluation loop without tool-plane approvals or events."""
    decks = list_pitchdecks()
    if not decks:
        return "No pitch decks found in input directory."

    instructions = (PROJECT_ROOT / "instructions" / "pitch_evaluator.md").read_text()
    agent = Agent(model=MODEL, instructions=instructions, output_type=str)

    results = []
    for deck in decks:
        log(1, f"Evaluating {deck['slug']} ({deck['file']})")
        prompt = build_user_prompt(
            "Evaluate this pitch deck.",
            [read_attachment(deck["file"])],
        )
        result = await agent.run(prompt)
        if VERBOSITY >= 3:
            log_llm_messages(list(result.all_messages()))
        report = result.output

        output_path = Path(deck["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        log(2, f"Wrote report to {output_path}")
        results.append(deck["slug"])

    return f"Evaluated {len(results)} pitch deck(s): {', '.join(results)}"


def cli_main() -> None:
    """Main entry point."""
    log(1, f"Starting raw Python run with MODEL={MODEL}, VERBOSITY={VERBOSITY}")
    log(1, f"Input directory: {INPUT_DIR}")
    log(1, f"Output directory: {OUTPUT_DIR}")
    log(1, "-" * 60)

    outcome = asyncio.run(evaluate_decks())
    print(outcome)


if __name__ == "__main__":
    cli_main()
