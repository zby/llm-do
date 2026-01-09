from pydantic_ai.toolsets import FunctionToolset

from llm_do.toolsets.approval import (
    get_toolset_approval_config,
    set_toolset_approval_config,
)


def test_get_toolset_approval_config_reads_attribute() -> None:
    toolset = FunctionToolset()
    config = {"echo": {"pre_approved": True}}
    set_toolset_approval_config(toolset, config)

    assert get_toolset_approval_config(toolset) == config


def test_get_toolset_approval_config_rejects_non_dict() -> None:
    toolset = FunctionToolset()
    toolset.__llm_do_approval_config__ = "bad"

    try:
        get_toolset_approval_config(toolset)
    except TypeError as exc:
        assert "__llm_do_approval_config__ must be a dict" in str(exc)
    else:
        raise AssertionError("Expected TypeError for invalid approval config")
