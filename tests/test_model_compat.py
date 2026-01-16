"""Tests for model compatibility checking."""
import pytest

from llm_do.models import (
    LLM_DO_MODEL_ENV,
    InvalidCompatibleModelsError,
    ModelCompatibilityError,
    ModelConfigError,
    NoModelError,
    get_env_model,
    get_model_string,
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
        validate_model_compatibility("openai:gpt-4o", None)  # should not raise

    def test_wildcard_allows_any(self):
        validate_model_compatibility("openai:gpt-4o", ["*"])  # should not raise

    def test_exact_match_valid(self):
        validate_model_compatibility("anthropic:claude-haiku-4-5", ["anthropic:claude-haiku-4-5"])

    def test_pattern_match_valid(self):
        validate_model_compatibility("anthropic:claude-haiku-4-5", ["anthropic:*"])

    def test_one_of_multiple_patterns_valid(self):
        validate_model_compatibility("openai:gpt-4o", ["anthropic:claude-haiku-4-5", "openai:gpt-4o", "google:gemini-pro"])

    def test_no_pattern_matches_invalid(self):
        with pytest.raises(ModelCompatibilityError, match="mistral:mistral-large") as exc:
            validate_model_compatibility("mistral:mistral-large", ["anthropic:*", "openai:*"], worker_name="test-worker")
        assert "test-worker" in str(exc.value)

    def test_empty_list_raises(self):
        with pytest.raises(InvalidCompatibleModelsError, match="empty compatible_models list"):
            validate_model_compatibility("openai:gpt-4o", [])

    def test_empty_list_error_includes_worker_name(self):
        with pytest.raises(InvalidCompatibleModelsError, match="my-worker"):
            validate_model_compatibility("openai:gpt-4o", [], worker_name="my-worker")


class TestSelectModel:
    """Tests for the model selection function."""

    def test_worker_model_takes_precedence_over_env(self, monkeypatch):
        """Worker model takes precedence over env fallback."""
        monkeypatch.setenv(LLM_DO_MODEL_ENV, "env:model")
        model = select_model(
            worker_model="anthropic:claude-haiku-4-5",
            compatible_models=None,
        )
        assert model == "anthropic:claude-haiku-4-5"

    def test_worker_model_when_no_env(self, monkeypatch):
        monkeypatch.delenv(LLM_DO_MODEL_ENV, raising=False)
        model = select_model(
            worker_model="anthropic:claude-haiku-4-5",
            compatible_models=None,
        )
        assert model == "anthropic:claude-haiku-4-5"

    def test_no_model_raises(self, monkeypatch):
        monkeypatch.delenv(LLM_DO_MODEL_ENV, raising=False)
        with pytest.raises(NoModelError, match="No model configured"):
            select_model(
                worker_model=None,
                compatible_models=None,
            )

    def test_env_model_validated_against_compatible(self, monkeypatch):
        monkeypatch.setenv(LLM_DO_MODEL_ENV, "anthropic:claude-haiku-4-5")
        model = select_model(
            worker_model=None,
            compatible_models=["anthropic:*"],
        )
        assert model == "anthropic:claude-haiku-4-5"

    def test_env_model_incompatible_raises(self, monkeypatch):
        monkeypatch.setenv(LLM_DO_MODEL_ENV, "openai:gpt-4o")
        with pytest.raises(ModelCompatibilityError, match="incompatible"):
            select_model(
                worker_model=None,
                compatible_models=["anthropic:*"],
            )

    def test_both_model_and_compatible_models_raises(self):
        """Cannot have both model and compatible_models set"""
        with pytest.raises(ModelConfigError, match="cannot have both"):
            select_model(
                worker_model="anthropic:claude-haiku-4-5",
                compatible_models=["anthropic:*"],
            )

    def test_empty_compatible_models_raises(self, monkeypatch):
        monkeypatch.setenv(LLM_DO_MODEL_ENV, "openai:gpt-4o")
        with pytest.raises(InvalidCompatibleModelsError, match="empty compatible_models"):
            select_model(
                worker_model=None,
                compatible_models=[],
            )

    def test_worker_name_in_error_message(self, monkeypatch):
        monkeypatch.setenv(LLM_DO_MODEL_ENV, "openai:gpt-4o")
        with pytest.raises(ModelCompatibilityError, match="my-worker"):
            select_model(
                worker_model=None,
                compatible_models=["anthropic:*"],
                worker_name="my-worker",
            )


class TestEnvVarModel:
    """Tests for LLM_DO_MODEL environment variable."""

    def test_get_env_model_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv(LLM_DO_MODEL_ENV, raising=False)
        assert get_env_model() is None

    def test_get_env_model_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv(LLM_DO_MODEL_ENV, "anthropic:claude-haiku-4-5")
        assert get_env_model() == "anthropic:claude-haiku-4-5"

    def test_env_var_used_as_fallback(self, monkeypatch):
        monkeypatch.setenv(LLM_DO_MODEL_ENV, "anthropic:claude-haiku-4-5")
        model = select_model(
            worker_model=None,
            compatible_models=None,
        )
        assert model == "anthropic:claude-haiku-4-5"

    def test_worker_overrides_env_var(self, monkeypatch):
        monkeypatch.setenv(LLM_DO_MODEL_ENV, "anthropic:claude-haiku-4-5")
        model = select_model(
            worker_model="openai:gpt-4o",
            compatible_models=None,
        )
        assert model == "openai:gpt-4o"

    def test_env_var_validated_against_compatible(self, monkeypatch):
        monkeypatch.setenv(LLM_DO_MODEL_ENV, "anthropic:claude-haiku-4-5")
        model = select_model(
            worker_model=None,
            compatible_models=["anthropic:*"],
        )
        assert model == "anthropic:claude-haiku-4-5"

    def test_env_var_incompatible_raises(self, monkeypatch):
        monkeypatch.setenv(LLM_DO_MODEL_ENV, "openai:gpt-4o")
        with pytest.raises(ModelCompatibilityError, match="incompatible"):
            select_model(
                worker_model=None,
                compatible_models=["anthropic:*"],
            )


class TestResolutionPrecedence:
    """Integration tests for the complete resolution precedence table."""

    def test_precedence_table(self, monkeypatch):
        """Test the resolution precedence as documented:
        1. Worker model (highest)
        2. LLM_DO_MODEL env var (lowest)
        """
        monkeypatch.setenv(LLM_DO_MODEL_ENV, "env:model")

        # Worker model overrides all
        assert select_model(
            worker_model="w",
            compatible_models=None
        ) == "w"

        # Env var last
        assert select_model(
            worker_model=None,
            compatible_models=None
        ) == "env:model"

    def test_validation_scenarios(self, monkeypatch):
        """Test validation matrix from discussion."""
        compatible = ["anthropic:claude-haiku-4-5", "openai:gpt-4o-mini"]

        # None compatible_models means any worker model works
        result = select_model(
            worker_model="random:model",
            compatible_models=None,
        )
        assert result == "random:model"

        # Env model in compatible list - succeeds
        monkeypatch.setenv(LLM_DO_MODEL_ENV, "openai:gpt-4o-mini")
        result = select_model(
            worker_model=None,
            compatible_models=compatible,
        )
        assert result == "openai:gpt-4o-mini"

        # Env model not in compatible list - fails
        monkeypatch.setenv(LLM_DO_MODEL_ENV, "openai:gpt-4o")
        with pytest.raises(ModelCompatibilityError):
            select_model(
                worker_model=None,
                compatible_models=compatible,
            )


class TestGetModelString:
    """Tests for get_model_string function that extracts canonical model strings."""

    def test_string_model_returned_as_is(self):
        """String models are returned unchanged."""
        assert get_model_string("anthropic:claude-haiku-4-5") == "anthropic:claude-haiku-4-5"
        assert get_model_string("openai:gpt-4o") == "openai:gpt-4o"
        assert get_model_string("test") == "test"

    def test_test_model(self):
        """TestModel produces 'test:test'."""
        from pydantic_ai.models.test import TestModel

        model = TestModel()
        assert get_model_string(model) == "test:test"

    def test_test_model_with_config(self):
        """Configured TestModel still produces 'test:test'."""
        from pydantic_ai.models.test import TestModel

        model = TestModel(custom_output_text="Hello!", call_tools=["foo"])
        assert get_model_string(model) == "test:test"

    def test_anthropic_model(self, monkeypatch):
        """AnthropicModel produces 'anthropic:model_name'."""
        from pydantic_ai import Agent

        # Set fake key if not present - we're only testing model string, not making calls
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-testing")
        agent = Agent("anthropic:claude-haiku-4-5")
        model = agent.model
        assert get_model_string(model) == "anthropic:claude-haiku-4-5"

    def test_anthropic_model_different_variant(self, monkeypatch):
        """Different Anthropic model variants work correctly."""
        from pydantic_ai import Agent

        monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-testing")
        agent = Agent("anthropic:claude-sonnet-4")
        model = agent.model
        assert get_model_string(model) == "anthropic:claude-sonnet-4"

    def test_model_string_works_with_validation(self):
        """get_model_string output works with validate_model_compatibility."""
        from pydantic_ai.models.test import TestModel

        model = TestModel()
        model_str = get_model_string(model)

        # Should match "test:*" pattern
        validate_model_compatibility(model_str, ["test:*"])  # should not raise

        # Should match "*" pattern
        validate_model_compatibility(model_str, ["*"])  # should not raise

        # Should not match "anthropic:*"
        with pytest.raises(ModelCompatibilityError):
            validate_model_compatibility(model_str, ["anthropic:*"])
