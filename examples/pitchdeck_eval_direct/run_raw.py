#!/usr/bin/env python
"""Pitch deck evaluation in raw Python (no llm-do tool plane).

Run with:
    uv run examples/pitchdeck_eval_direct/run_raw.py
    python examples/pitchdeck_eval_direct/run_raw.py
"""

import asyncio
import mimetypes
from pathlib import Path

try:
    from slugify import slugify
except ImportError:
    raise ImportError("python-slugify required. Install with: pip install python-slugify")

from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent, UserContent

# =============================================================================
# CONFIGURATION
# =============================================================================

MODEL = "anthropic:claude-haiku-4-5"
VERBOSITY = 1

# =============================================================================
# Paths
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.resolve()
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "evaluations"


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

    media_type, _ = mimetypes.guess_type(str(file_path))
    if media_type is None:
        media_type = "application/octet-stream"

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
        if VERBOSITY >= 1:
            print(f"Evaluating {deck['slug']} ({deck['file']})")
        prompt = build_user_prompt(
            "Evaluate this pitch deck.",
            [read_attachment(deck["file"])],
        )
        result = await agent.run(prompt)
        report = result.output

        output_path = Path(deck["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        results.append(deck["slug"])

    return f"Evaluated {len(results)} pitch deck(s): {', '.join(results)}"


def cli_main() -> None:
    """Main entry point."""
    print(f"Starting raw Python run with MODEL={MODEL}, VERBOSITY={VERBOSITY}")
    print(f"Input directory: {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print("-" * 60)

    outcome = asyncio.run(evaluate_decks())
    print(outcome)


if __name__ == "__main__":
    cli_main()
