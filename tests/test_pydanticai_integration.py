"""Integration tests using mocked LLM models with predefined tool calls.

Note: Basic approve_all and strict_mode tests are in test_pydanticai_base.py.
This file focuses on multi-step integration scenarios.
"""
from pathlib import Path

import pytest

from llm_do import (
    ApprovalController,
    ApprovalDecision,
    WorkerDefinition,
    WorkerRegistry,
    run_worker,
)
from pydantic_ai_blocking_approval import ApprovalRequest


def _project_root(tmp_path):
    root = tmp_path / "project"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def registry(tmp_path):
    return WorkerRegistry(_project_root(tmp_path))






