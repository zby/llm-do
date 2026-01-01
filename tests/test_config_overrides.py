"""Tests for CLI configuration overrides (--set flag)."""
import pytest

from llm_do.config import (
    apply_overrides,
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
        key, value = parse_set_override("toolsets.shell.timeout=30")
        assert key == "toolsets.shell.timeout"
        assert value == 30

    def test_parse_boolean_true(self):
        for val_str in ["true", "True", "TRUE", "yes", "on"]:
            key, value = parse_set_override(f"flag={val_str}")
            assert value is True, f"Failed for {val_str}"

    def test_parse_boolean_false(self):
        for val_str in ["false", "False", "FALSE", "no", "off"]:
            key, value = parse_set_override(f"flag={val_str}")
            assert value is False, f"Failed for {val_str}"

    def test_parse_integer(self):
        key, value = parse_set_override("max_count=10")
        assert key == "max_count"
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

    @pytest.mark.parametrize("initial,key,value,expected", [
        # Update existing nested field
        ({"toolsets": {"shell": {"timeout": 30}}},
         "toolsets.shell.timeout", 60,
         {"toolsets": {"shell": {"timeout": 60}}}),
        # Create nested structure from empty
        ({}, "toolsets.shell.timeout", 30,
         {"toolsets": {"shell": {"timeout": 30}}}),
        # Deep nesting
        ({}, "a.b.c.d", "value",
         {"a": {"b": {"c": {"d": "value"}}}}),
        # Add to existing nested, preserving other fields
        ({"toolsets": {"shell": {"timeout": 30, "other": "keep"}}},
         "toolsets.shell.rules", [{"pattern": "git"}],
         {"toolsets": {"shell": {"timeout": 30, "other": "keep", "rules": [{"pattern": "git"}]}}}),
        # Bracketed literal key for class-path toolsets
        ({},
         'toolsets["llm_do.toolsets.shell.ShellToolset"].default.approval_required', False,
         {"toolsets": {"llm_do.toolsets.shell.ShellToolset": {"default": {"approval_required": False}}}}),
    ])
    def test_apply_nested_override(self, initial, key, value, expected):
        apply_set_override(initial, key, value)
        assert initial == expected

    def test_apply_override_fails_on_non_dict(self):
        data = {"model": "string-value"}
        with pytest.raises(ValueError, match="Cannot navigate through non-dict"):
            apply_set_override(data, "model.nested", "value")


class TestApplyOverrides:
    """Tests for applying multiple overrides."""

    def test_apply_no_overrides(self):
        data = {"name": "test", "model": "old"}
        result = apply_overrides(data, set_overrides=[])
        assert result == {"name": "test", "model": "old"}

    def test_apply_model_override(self):
        data = {"name": "test", "model": "old-model"}
        result = apply_overrides(data, set_overrides=["model=new-model"])
        assert result["model"] == "new-model"

    def test_apply_multiple_overrides(self):
        data = {"name": "test"}
        result = apply_overrides(
            data,
            set_overrides=[
                "model=openai:gpt-4o",
                "description=Updated description",
            ]
        )
        assert result["model"] == "openai:gpt-4o"
        assert result["description"] == "Updated description"

    def test_apply_nested_override(self):
        data = {"name": "test"}
        result = apply_overrides(
            data,
            set_overrides=["toolsets.shell.timeout=30"]
        )
        assert result["toolsets"]["shell"]["timeout"] == 30

    def test_last_override_wins(self):
        data = {"name": "test", "model": "original"}
        result = apply_overrides(
            data,
            set_overrides=["model=first", "model=second", "model=third"]
        )
        assert result["model"] == "third"

    def test_invalid_override_raises(self):
        data = {"name": "test"}
        with pytest.raises(ValueError, match="Invalid --set override"):
            apply_overrides(data, set_overrides=["invalid syntax"])

    def test_override_preserves_other_fields(self):
        data = {
            "name": "test",
            "instructions": "original instructions",
            "description": "original description",
            "model": "original-model",
        }
        result = apply_overrides(data, set_overrides=["model=new-model"])
        assert result["name"] == "test"
        assert result["instructions"] == "original instructions"
        assert result["description"] == "original description"
        assert result["model"] == "new-model"

    def test_does_not_modify_original(self):
        data = {"name": "test", "model": "old"}
        result = apply_overrides(data, set_overrides=["model=new"])
        assert data["model"] == "old"  # Original unchanged
        assert result["model"] == "new"


class TestIntegration:
    """Integration tests for realistic override scenarios."""

    def test_toolsets_override(self):
        """Test overriding toolsets configuration."""
        data = {
            "name": "worker",
            "instructions": "Test",
            "toolsets": {"shell": {"rules": []}},
        }
        result = apply_overrides(
            data,
            set_overrides=['toolsets.shell.rules=[{"pattern": "git"}]']
        )
        assert result["toolsets"]["shell"]["rules"] == [{"pattern": "git"}]

    def test_class_path_toolset_override(self):
        """Test overriding class-path toolset configuration."""
        data = {"name": "worker"}
        result = apply_overrides(
            data,
            set_overrides=[
                'toolsets["llm_do.toolsets.shell.ShellToolset"].default.approval_required=false'
            ],
        )
        assert result["toolsets"]["llm_do.toolsets.shell.ShellToolset"]["default"]["approval_required"] is False

    def test_development_model_swap(self):
        """Test swapping model for local testing."""
        data = {
            "name": "worker",
            "instructions": "Test",
            "model": "openai:gpt-4",
        }
        result = apply_overrides(
            data,
            set_overrides=["model=anthropic:claude-sonnet-4"]
        )
        assert result["model"] == "anthropic:claude-sonnet-4"

    def test_complex_nested_override(self):
        """Test complex nested structure creation."""
        data = {"name": "worker"}
        result = apply_overrides(
            data,
            set_overrides=[
                "toolsets.shell.rules=[{\"pattern\": \"git *\"}]",
                "toolsets.shell.timeout=60",
                "toolsets.filesystem.allowed_paths=[\"/tmp\"]",
            ]
        )
        assert result["toolsets"]["shell"]["rules"] == [{"pattern": "git *"}]
        assert result["toolsets"]["shell"]["timeout"] == 60
        assert result["toolsets"]["filesystem"]["allowed_paths"] == ["/tmp"]
