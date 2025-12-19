"""Tests for CLI configuration overrides (--set flag)."""
import pytest

from llm_do import WorkerDefinition
from llm_do.config_overrides import (
    apply_cli_overrides,
    apply_set_override,
    parse_set_override,
)


class TestParseSetOverride:
    """Tests for parsing --set KEY=VALUE specifications."""

    def test_parse_simple_string(self):
        key, value = parse_set_override("model=gpt-4")
        assert key == "model"
        assert value == "gpt-4"

    def test_parse_nested_key(self):
        key, value = parse_set_override("attachment_policy.max_attachments=10")
        assert key == "attachment_policy.max_attachments"
        assert value == 10

    def test_parse_boolean_true(self):
        for val_str in ["true", "True", "TRUE", "yes", "on"]:
            key, value = parse_set_override(f"flag={val_str}")
            assert value is True, f"Failed for {val_str}"

    def test_parse_boolean_false(self):
        for val_str in ["false", "False", "FALSE", "no", "off"]:
            key, value = parse_set_override(f"flag={val_str}")
            assert value is False, f"Failed for {val_str}"

    def test_parse_integer(self):
        key, value = parse_set_override("max_attachments=10")
        assert key == "max_attachments"
        assert value == 10
        assert isinstance(value, int)

    def test_parse_float(self):
        key, value = parse_set_override("threshold=3.14")
        assert key == "threshold"
        assert value == 3.14
        assert isinstance(value, float)

    def test_parse_json_list(self):
        key, value = parse_set_override('tags=["a", "b", "c"]')
        assert key == "tags"
        assert value == ["a", "b", "c"]

    def test_parse_json_dict(self):
        key, value = parse_set_override('config={"key": "value"}')
        assert key == "config"
        assert value == {"key": "value"}

    def test_parse_empty_value(self):
        key, value = parse_set_override("field=")
        assert key == "field"
        assert value == ""

    def test_parse_value_with_equals(self):
        # Value contains '=' - should only split on first '='
        key, value = parse_set_override("url=https://example.com?param=value")
        assert key == "url"
        assert value == "https://example.com?param=value"

    def test_parse_missing_equals(self):
        with pytest.raises(ValueError, match="Invalid --set format.*Expected KEY=VALUE"):
            parse_set_override("invalid")

    def test_parse_empty_key(self):
        with pytest.raises(ValueError, match="Empty key"):
            parse_set_override("=value")


class TestApplySetOverride:
    """Tests for applying overrides to dictionaries."""

    def test_apply_simple_override(self):
        data = {"model": "old"}
        apply_set_override(data, "model", "new")
        assert data["model"] == "new"

    def test_apply_nested_override_existing(self):
        data = {"attachment_policy": {"max_attachments": 4}}
        apply_set_override(data, "attachment_policy.max_attachments", 10)
        assert data["attachment_policy"]["max_attachments"] == 10

    def test_apply_nested_override_creates_dict(self):
        data = {}
        apply_set_override(data, "attachment_policy.max_attachments", 10)
        assert data == {"attachment_policy": {"max_attachments": 10}}

    def test_apply_deep_nested_override(self):
        data = {}
        apply_set_override(data, "a.b.c.d", "value")
        assert data == {"a": {"b": {"c": {"d": "value"}}}}

    def test_apply_override_to_existing_nested(self):
        data = {"attachment_policy": {"max_attachments": 4, "other": "keep"}}
        apply_set_override(data, "attachment_policy.allowed_suffixes", [".txt", ".md"])
        assert data["attachment_policy"]["max_attachments"] == 4
        assert data["attachment_policy"]["other"] == "keep"
        assert data["attachment_policy"]["allowed_suffixes"] == [".txt", ".md"]

    def test_apply_override_fails_on_non_dict(self):
        data = {"model": "string-value"}
        with pytest.raises(ValueError, match="Cannot navigate through non-dict"):
            apply_set_override(data, "model.nested", "value")


class TestApplyCliOverrides:
    """Tests for applying overrides to WorkerDefinition."""

    def test_apply_no_overrides(self):
        defn = WorkerDefinition(name="test", instructions="test")
        result = apply_cli_overrides(defn, set_overrides=[])
        assert result.name == "test"
        assert result.instructions == "test"

    def test_apply_model_override(self):
        defn = WorkerDefinition(name="test", instructions="test", model="old-model")
        result = apply_cli_overrides(defn, set_overrides=["model=new-model"])
        assert result.model == "new-model"

    def test_apply_multiple_overrides(self):
        defn = WorkerDefinition(name="test", instructions="test")
        result = apply_cli_overrides(
            defn,
            set_overrides=[
                "model=openai:gpt-4o",
                "description=Updated description",
                "locked=true",
            ]
        )
        assert result.model == "openai:gpt-4o"
        assert result.description == "Updated description"
        assert result.locked is True

    def test_apply_nested_override(self):
        defn = WorkerDefinition(name="test", instructions="test")
        result = apply_cli_overrides(
            defn,
            set_overrides=["attachment_policy.max_attachments=10"]
        )
        assert result.attachment_policy.max_attachments == 10

    def test_last_override_wins(self):
        defn = WorkerDefinition(name="test", instructions="test", model="original")
        result = apply_cli_overrides(
            defn,
            set_overrides=["model=first", "model=second", "model=third"]
        )
        assert result.model == "third"

    def test_invalid_override_raises(self):
        defn = WorkerDefinition(name="test", instructions="test")
        with pytest.raises(ValueError, match="Invalid --set override"):
            apply_cli_overrides(defn, set_overrides=["invalid syntax"])

    def test_schema_violation_raises(self):
        defn = WorkerDefinition(name="test", instructions="test")
        # Try to set a field to an invalid type
        with pytest.raises(ValueError, match="invalid worker configuration"):
            apply_cli_overrides(
                defn,
                set_overrides=["attachment_policy.max_attachments=not-a-number"]
            )

    def test_override_toolset_field(self):
        defn = WorkerDefinition(
            name="test",
            instructions="test",
            toolsets={"delegation": {}},
        )
        result = apply_cli_overrides(
            defn,
            set_overrides=['toolsets.delegation.summarizer={}']
        )
        assert result.toolsets["delegation"]["summarizer"] == {}

    def test_override_boolean_field(self):
        defn = WorkerDefinition(name="test", instructions="test", locked=False)
        result = apply_cli_overrides(defn, set_overrides=["locked=true"])
        assert result.locked is True

    def test_override_preserves_other_fields(self):
        defn = WorkerDefinition(
            name="test",
            instructions="original instructions",
            description="original description",
            model="original-model",
            locked=False,
        )
        result = apply_cli_overrides(defn, set_overrides=["model=new-model"])
        assert result.name == "test"
        assert result.instructions == "original instructions"
        assert result.description == "original description"
        assert result.model == "new-model"
        assert result.locked is False


class TestIntegration:
    """Integration tests for realistic override scenarios."""

    def test_production_hardening_scenario(self):
        """Test hardening a worker for production deployment."""
        defn = WorkerDefinition(
            name="worker",
            instructions="Do work",
            model="anthropic:claude-haiku-4-5",
        )
        result = apply_cli_overrides(
            defn,
            set_overrides=[
                "locked=true",
                "attachment_policy.max_attachments=1",
                "attachment_policy.max_total_bytes=1000000",
            ]
        )
        assert result.locked is True
        assert result.attachment_policy.max_attachments == 1
        assert result.attachment_policy.max_total_bytes == 1000000

    def test_development_model_swap(self):
        """Test swapping model for local testing."""
        defn = WorkerDefinition(
            name="worker",
            instructions="Test",
            model="openai:gpt-4",
        )
        result = apply_cli_overrides(
            defn,
            set_overrides=["model=anthropic:claude-sonnet-4"]
        )
        assert result.model == "anthropic:claude-sonnet-4"

    def test_toolsets_override(self):
        """Test overriding toolsets configuration."""
        defn = WorkerDefinition(
            name="worker",
            instructions="Test",
            toolsets={"shell": {"rules": []}},
        )
        result = apply_cli_overrides(
            defn,
            set_overrides=['toolsets.shell.rules=[{"pattern": "git"}]']
        )
        assert result.toolsets["shell"]["rules"] == [{"pattern": "git"}]
