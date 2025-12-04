"""Tests for model compatibility checking."""
import pytest

from llm_do.model_compat import (
    InvalidCompatibleModelsError,
    ModelCompatibilityError,
    ModelValidationResult,
    NoModelError,
    model_matches_pattern,
    select_model,
    validate_model_compatibility,
)


class TestModelMatchesPattern:
    """Tests for the pattern matching function."""

    def test_exact_match(self):
        assert model_matches_pattern("anthropic:claude-haiku-4-5", "anthropic:claude-haiku-4-5")

    def test_exact_match_case_insensitive(self):
        assert model_matches_pattern("Anthropic:Claude-Haiku-4-5", "anthropic:claude-haiku-4-5")

    def test_wildcard_all(self):
        assert model_matches_pattern("anthropic:claude-sonnet-4", "*")
        assert model_matches_pattern("openai:gpt-4o", "*")

    def test_provider_wildcard(self):
        assert model_matches_pattern("anthropic:claude-sonnet-4", "anthropic:*")
        assert model_matches_pattern("anthropic:claude-haiku-4-5", "anthropic:*")
        assert not model_matches_pattern("openai:gpt-4o", "anthropic:*")

    def test_model_family_wildcard(self):
        assert model_matches_pattern("anthropic:claude-haiku-4-5", "anthropic:claude-haiku-*")
        assert model_matches_pattern("anthropic:claude-haiku-4-5-20250929", "anthropic:claude-haiku-*")
        assert not model_matches_pattern("anthropic:claude-sonnet-4", "anthropic:claude-haiku-*")

    def test_no_match(self):
        assert not model_matches_pattern("openai:gpt-4o", "anthropic:claude-sonnet-4")

    def test_partial_match_requires_wildcard(self):
        # Without wildcard, partial strings don't match
        assert not model_matches_pattern("anthropic:claude-haiku-4-5", "anthropic:claude")
        # With wildcard, they do
        assert model_matches_pattern("anthropic:claude-haiku-4-5", "anthropic:claude*")


class TestValidateModelCompatibility:
    """Tests for the validation function."""

    def test_none_compatible_models_allows_any(self):
        result = validate_model_compatibility("openai:gpt-4o", None)
        assert result.valid is True
        assert result.model == "openai:gpt-4o"

    def test_wildcard_allows_any(self):
        result = validate_model_compatibility("openai:gpt-4o", ["*"])
        assert result.valid is True

    def test_exact_match_valid(self):
        result = validate_model_compatibility(
            "anthropic:claude-haiku-4-5",
            ["anthropic:claude-haiku-4-5"]
        )
        assert result.valid is True

    def test_pattern_match_valid(self):
        result = validate_model_compatibility(
            "anthropic:claude-haiku-4-5",
            ["anthropic:*"]
        )
        assert result.valid is True

    def test_one_of_multiple_patterns_valid(self):
        result = validate_model_compatibility(
            "openai:gpt-4o",
            ["anthropic:claude-haiku-4-5", "openai:gpt-4o", "google:gemini-pro"]
        )
        assert result.valid is True

    def test_no_pattern_matches_invalid(self):
        result = validate_model_compatibility(
            "mistral:mistral-large",
            ["anthropic:*", "openai:*"],
            worker_name="test-worker",
        )
        assert result.valid is False
        assert "mistral:mistral-large" in result.message
        assert "test-worker" in result.message

    def test_empty_list_raises(self):
        with pytest.raises(InvalidCompatibleModelsError, match="empty compatible_models list"):
            validate_model_compatibility("openai:gpt-4o", [])

    def test_empty_list_error_includes_worker_name(self):
        with pytest.raises(InvalidCompatibleModelsError, match="my-worker"):
            validate_model_compatibility("openai:gpt-4o", [], worker_name="my-worker")


class TestSelectModel:
    """Tests for the model selection function."""

    def test_worker_model_takes_precedence(self):
        model = select_model(
            worker_model="anthropic:claude-haiku-4-5",
            cli_model="openai:gpt-4o",
            caller_model="anthropic:claude-sonnet-4",
            compatible_models=None,
        )
        assert model == "anthropic:claude-haiku-4-5"

    def test_cli_model_when_no_worker_model(self):
        model = select_model(
            worker_model=None,
            cli_model="openai:gpt-4o",
            caller_model="anthropic:claude-sonnet-4",
            compatible_models=None,
        )
        assert model == "openai:gpt-4o"

    def test_caller_model_when_no_worker_or_cli(self):
        model = select_model(
            worker_model=None,
            cli_model=None,
            caller_model="anthropic:claude-sonnet-4",
            compatible_models=None,
        )
        assert model == "anthropic:claude-sonnet-4"

    def test_no_model_raises(self):
        with pytest.raises(NoModelError, match="No model configured"):
            select_model(
                worker_model=None,
                cli_model=None,
                caller_model=None,
                compatible_models=None,
            )

    def test_cli_model_validated_against_compatible(self):
        model = select_model(
            worker_model=None,
            cli_model="anthropic:claude-haiku-4-5",
            caller_model=None,
            compatible_models=["anthropic:*"],
        )
        assert model == "anthropic:claude-haiku-4-5"

    def test_cli_model_incompatible_raises(self):
        with pytest.raises(ModelCompatibilityError, match="not compatible"):
            select_model(
                worker_model=None,
                cli_model="openai:gpt-4o",
                caller_model=None,
                compatible_models=["anthropic:*"],
            )

    def test_caller_model_validated_against_compatible(self):
        model = select_model(
            worker_model=None,
            cli_model=None,
            caller_model="anthropic:claude-haiku-4-5",
            compatible_models=["anthropic:*"],
        )
        assert model == "anthropic:claude-haiku-4-5"

    def test_caller_model_incompatible_raises(self):
        with pytest.raises(ModelCompatibilityError, match="not compatible"):
            select_model(
                worker_model=None,
                cli_model=None,
                caller_model="openai:gpt-4o",
                compatible_models=["anthropic:*"],
            )

    def test_worker_model_bypasses_validation(self):
        # Worker's own model is trusted and not validated against compatible_models
        # This allows worker authors to lock in a specific model
        model = select_model(
            worker_model="mistral:mistral-large",
            cli_model=None,
            caller_model=None,
            compatible_models=["anthropic:*"],  # Would reject mistral
        )
        assert model == "mistral:mistral-large"

    def test_empty_compatible_models_raises(self):
        with pytest.raises(InvalidCompatibleModelsError, match="empty compatible_models"):
            select_model(
                worker_model=None,
                cli_model="openai:gpt-4o",
                caller_model=None,
                compatible_models=[],
            )

    def test_worker_name_in_error_message(self):
        with pytest.raises(ModelCompatibilityError, match="my-worker"):
            select_model(
                worker_model=None,
                cli_model="openai:gpt-4o",
                caller_model=None,
                compatible_models=["anthropic:*"],
                worker_name="my-worker",
            )


class TestResolutionPrecedence:
    """Integration tests for the complete resolution precedence table."""

    def test_precedence_table(self):
        """Test the resolution precedence as documented."""
        # Worker model always wins
        assert select_model(
            worker_model="w", cli_model="c", caller_model="p",
            compatible_models=None
        ) == "w"

        # CLI next if worker not set
        assert select_model(
            worker_model=None, cli_model="c", caller_model="p",
            compatible_models=None
        ) == "c"

        # Caller last
        assert select_model(
            worker_model=None, cli_model=None, caller_model="p",
            compatible_models=None
        ) == "p"

    def test_validation_scenarios(self):
        """Test validation matrix from discussion."""
        compatible = ["anthropic:claude-haiku-4-5", "openai:gpt-4o-mini"]

        # Empty compatible list - uses worker default (first in list? no - None means any)
        # Actually with compatible_models=None, any model works
        result = select_model(
            worker_model=None,
            cli_model="random:model",
            caller_model=None,
            compatible_models=None,  # None means any
        )
        assert result == "random:model"

        # CLI model in compatible list - succeeds
        result = select_model(
            worker_model=None,
            cli_model="openai:gpt-4o-mini",
            caller_model=None,
            compatible_models=compatible,
        )
        assert result == "openai:gpt-4o-mini"

        # CLI model not in compatible list - fails
        with pytest.raises(ModelCompatibilityError):
            select_model(
                worker_model=None,
                cli_model="openai:gpt-4o",  # Not gpt-4o-mini
                caller_model=None,
                compatible_models=compatible,
            )
