"""Shared pytest fixtures for pitchdeck evaluation tests"""

import pytest
import tempfile
from pathlib import Path
import sys

# Add parent directory to path to import tools.py
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


@pytest.fixture
def pitchdeck_workspace():
    """
    Provide temporary workspace with pitchdeck directory structure
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Create directory structure
        (workspace / "pipeline").mkdir()
        (workspace / "portfolio").mkdir()
        (workspace / "framework").mkdir()

        # Create sample framework file
        framework_path = workspace / "framework" / "eval_pitchdeck.md"
        framework_path.write_text("""# Pitchdeck Evaluation Framework

## Evaluation Areas

1. **Problem & Solution**
2. **Market Opportunity**
3. **Traction & Metrics**
4. **Team**
5. **Business Model**
6. **Competitive Advantage**
7. **Financials & Ask**
8. **Overall Assessment**
""")

        yield workspace


@pytest.fixture
def sample_pdf_files(pitchdeck_workspace):
    """Create sample PDF files in pipeline directory"""
    pipeline = pitchdeck_workspace / "pipeline"

    # Create dummy PDF files (just text files for testing)
    pdf1 = pipeline / "Startup One (YC S24).pdf"
    pdf1.write_text("Sample PDF content for Startup One")

    pdf2 = pipeline / "Company Two - Deck.pdf"
    pdf2.write_text("Sample PDF content for Company Two")

    return [pdf1, pdf2]


@pytest.fixture
def pitchdeck_toolbox(pitchdeck_workspace):
    """Provide PitchdeckToolbox instance"""
    from examples.pitchdeck_eval.tools import PitchdeckToolbox
    return PitchdeckToolbox(working_dir=pitchdeck_workspace)
