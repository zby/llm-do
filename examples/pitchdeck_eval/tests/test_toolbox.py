"""Tests for PitchdeckToolbox"""

import pytest
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from examples.pitchdeck_eval.tools import PitchdeckToolbox


class TestPitchdeckToolbox:
    """Tests for PitchdeckToolbox class"""

    def test_inherits_from_base_toolbox(self, pitchdeck_toolbox):
        """Test that PitchdeckToolbox inherits BaseToolbox methods"""
        assert hasattr(pitchdeck_toolbox, 'run_bash')
        assert hasattr(pitchdeck_toolbox, 'read_file')
        assert hasattr(pitchdeck_toolbox, 'write_file')

    def test_has_normalize_filename_method(self, pitchdeck_toolbox):
        """Test that PitchdeckToolbox has normalize_filename method"""
        assert hasattr(pitchdeck_toolbox, 'normalize_filename')
        assert callable(pitchdeck_toolbox.normalize_filename)


class TestNormalizeFilename:
    """Tests for normalize_filename method"""

    def test_removes_pdf_extension_lowercase(self, pitchdeck_toolbox):
        """Test that .pdf extension is removed"""
        result = pitchdeck_toolbox.normalize_filename("Company.pdf")
        assert result == "Company"
        assert not result.endswith('.pdf')

    def test_removes_pdf_extension_uppercase(self, pitchdeck_toolbox):
        """Test that .PDF extension is removed"""
        result = pitchdeck_toolbox.normalize_filename("Company.PDF")
        assert result == "Company"
        assert not result.endswith('.PDF')

    def test_removes_spaces(self, pitchdeck_toolbox):
        """Test that spaces are removed"""
        result = pitchdeck_toolbox.normalize_filename("Company Name.pdf")
        assert result == "CompanyName"
        assert ' ' not in result

    def test_removes_special_characters(self, pitchdeck_toolbox):
        """Test that special characters are removed"""
        result = pitchdeck_toolbox.normalize_filename("Company@#$%.pdf")
        assert result == "Company"

    def test_preserves_hyphens(self, pitchdeck_toolbox):
        """Test that hyphens are preserved"""
        result = pitchdeck_toolbox.normalize_filename("Real-Research.pdf")
        assert result == "Real-Research"
        assert '-' in result

    def test_removes_underscores(self, pitchdeck_toolbox):
        """Test that underscores are removed"""
        result = pitchdeck_toolbox.normalize_filename("Company_Name.pdf")
        assert result == "CompanyName"
        assert '_' not in result

    def test_preserves_numbers(self, pitchdeck_toolbox):
        """Test that numbers are preserved"""
        result = pitchdeck_toolbox.normalize_filename("Company123.pdf")
        assert result == "Company123"

    def test_yc_batch_format(self, pitchdeck_toolbox):
        """Test YC batch format normalization"""
        result = pitchdeck_toolbox.normalize_filename("Real Research (YC S24).pdf")
        assert result == "RealResearchYCS24"

    def test_multiple_words_with_spaces(self, pitchdeck_toolbox):
        """Test multiple words with spaces"""
        result = pitchdeck_toolbox.normalize_filename("My Awesome Startup.pdf")
        assert result == "MyAwesomeStartup"

    def test_hyphens_and_spaces(self, pitchdeck_toolbox):
        """Test filename with both hyphens and spaces"""
        result = pitchdeck_toolbox.normalize_filename("Startup - Deck 2024.pdf")
        assert result == "Startup-Deck2024"

    def test_version_numbers(self, pitchdeck_toolbox):
        """Test handling of version numbers"""
        result = pitchdeck_toolbox.normalize_filename("Company.v2.pdf")
        assert result == "Companyv2"

    def test_parentheses_removed(self, pitchdeck_toolbox):
        """Test that parentheses are removed"""
        result = pitchdeck_toolbox.normalize_filename("Company (Batch 2024).pdf")
        assert result == "CompanyBatch2024"
        assert '(' not in result
        assert ')' not in result

    def test_complex_real_world_example(self, pitchdeck_toolbox):
        """Test complex real-world filename"""
        result = pitchdeck_toolbox.normalize_filename(
            "Startup Name (Batch 2024) - Deck.pdf"
        )
        assert result == "StartupNameBatch2024-Deck"

    def test_empty_result_handling(self, pitchdeck_toolbox):
        """Test handling of files that would result in empty name"""
        result = pitchdeck_toolbox.normalize_filename("@#$%.pdf")
        # Should at least not crash, even if result is empty
        assert isinstance(result, str)


class TestToolboxIntegration:
    """Integration tests for toolbox functionality"""

    def test_can_read_framework_file(self, pitchdeck_toolbox, pitchdeck_workspace):
        """Test that toolbox can read framework file"""
        result = pitchdeck_toolbox.read_file("framework/eval_pitchdeck.md")
        assert "Evaluation Areas" in result
        assert "Problem & Solution" in result

    def test_can_create_company_directory(self, pitchdeck_toolbox, pitchdeck_workspace):
        """Test that toolbox can create directories via bash"""
        company_name = "TestCompany"
        result = pitchdeck_toolbox.run_bash(f"mkdir -p portfolio/{company_name}")

        # Verify directory was created
        company_dir = pitchdeck_workspace / "portfolio" / company_name
        assert company_dir.exists()
        assert company_dir.is_dir()

    def test_can_write_evaluation_file(self, pitchdeck_toolbox, pitchdeck_workspace):
        """Test that toolbox can write evaluation files"""
        company_name = "TestCompany"
        (pitchdeck_workspace / "portfolio" / company_name).mkdir(parents=True)

        evaluation_content = "# Evaluation for TestCompany\n\nThis is a test."
        result = pitchdeck_toolbox.write_file(
            f"portfolio/{company_name}/{company_name}-Evaluation.md",
            evaluation_content
        )

        # Verify file was created
        eval_file = (
            pitchdeck_workspace / "portfolio" / company_name
            / f"{company_name}-Evaluation.md"
        )
        assert eval_file.exists()
        assert eval_file.read_text() == evaluation_content

    def test_can_list_pdf_files(self, pitchdeck_toolbox, sample_pdf_files):
        """Test that toolbox can list PDF files"""
        result = pitchdeck_toolbox.run_bash("find pipeline/ -name '*.pdf'")

        # Should find both PDF files
        assert "Startup One (YC S24).pdf" in result
        assert "Company Two - Deck.pdf" in result

    def test_normalize_and_create_workflow(
        self, pitchdeck_toolbox, pitchdeck_workspace, sample_pdf_files
    ):
        """Test workflow: normalize filename and create portfolio directory"""
        # Get first PDF filename
        pdf_file = sample_pdf_files[0]
        filename = pdf_file.name

        # Normalize filename to get company name
        company_name = pitchdeck_toolbox.normalize_filename(filename)
        assert company_name == "StartupOneYCS24"

        # Create portfolio directory
        pitchdeck_toolbox.run_bash(f"mkdir -p portfolio/{company_name}")

        # Verify directory exists
        company_dir = pitchdeck_workspace / "portfolio" / company_name
        assert company_dir.exists()
