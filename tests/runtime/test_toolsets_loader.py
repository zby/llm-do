from llm_do.toolsets.loader import extract_toolset_approval_configs


def test_extract_toolset_approval_configs_by_name() -> None:
    toolsets = {
        "shell": {"_approval_config": {"safe_tool": {"pre_approved": True}}},
        "filesystem": {},
        "custom": {"_approval_config": {"blocked": {"blocked": True}}},
    }

    configs = extract_toolset_approval_configs(toolsets)

    assert configs == {
        "shell": {"safe_tool": {"pre_approved": True}},
        "custom": {"blocked": {"blocked": True}},
    }
