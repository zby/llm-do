"""Tool registration for llm-do workers.

Note: All tools are now provided via toolsets in execution.py:
- FileSandboxApprovalToolset for file operations (read_file, write_file, etc.)
- ShellApprovalToolset for shell commands
- DelegationApprovalToolset for worker_call, worker_create
- CustomApprovalToolset for custom tools from tools.py

This module is kept for backward compatibility but may be removed in future.
"""
from __future__ import annotations

# This module is intentionally minimal.
# All tool registration is now handled via toolsets in execution.py.
