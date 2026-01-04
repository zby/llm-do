from llm_do.toolsets.loader import extract_toolset_approval_configs


def test_extract_toolset_approval_configs_preserves_order() -> None:
    toolsets = {
        "shell": {"_approval_config": {"safe_tool": {"pre_approved": True}}},
        "filesystem": {},
        "custom": {"_approval_config": {"blocked": {"blocked": True}}},
    }

    configs = extract_toolset_approval_configs(toolsets)

    assert configs == [
        {"safe_tool": {"pre_approved": True}},
        None,
        {"blocked": {"blocked": True}},
    ]
