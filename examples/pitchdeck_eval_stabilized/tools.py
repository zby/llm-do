"""Custom tools for pitch deck evaluation workflow.

This demonstrates "stabilizing" - extracting deterministic logic from LLM
instructions into Python tools. The list_pitchdecks function handles
file discovery and slug generation, which are purely mechanical operations
that don't benefit from LLM reasoning.
"""

from pathlib import Path

from pydantic_ai.toolsets import FunctionToolset

from llm_do.runtime import ToolsetSpec
from llm_do.toolsets.approval import set_toolset_approval_config

try:
    from slugify import slugify
except ImportError:
    raise ImportError(
        "python-slugify required. Install with: pip install python-slugify"
    )


def build_pitchdeck_tools():
    pitchdeck_tools = FunctionToolset()

    @pitchdeck_tools.tool
    def list_pitchdecks(path: str = "input") -> list[dict]:
        """List pitch deck PDFs with pre-computed slugs and output paths.

        Args:
            path: Directory to scan for PDF files. Defaults to "input".

        Returns:
            List of dicts with keys:
            - file: Path to the PDF file
            - slug: URL-safe slug derived from filename
            - output_path: Suggested output path for the evaluation report
        """
        result = []
        for pdf in sorted(Path(path).glob("*.pdf")):
            slug = slugify(pdf.stem)
            result.append({
                "file": str(pdf),
                "slug": slug,
                "output_path": f"evaluations/{slug}.md",
            })
        return result

    set_toolset_approval_config(
        pitchdeck_tools,
        {"list_pitchdecks": {"pre_approved": True}},
    )

    return pitchdeck_tools


pitchdeck_tools = ToolsetSpec(factory=build_pitchdeck_tools)
