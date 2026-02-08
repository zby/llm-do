"""Dependency direction checks for runtime boundary enforcement."""
from __future__ import annotations

import ast
from pathlib import Path

RUNTIME_DIR = Path(__file__).resolve().parents[2] / "llm_do" / "runtime"
FORBIDDEN_PREFIXES = (
    "llm_do.project",
    "llm_do.cli",
    "llm_do.ui",
    "llm_do.toolsets.loader",
    "llm_do.toolsets.builtins",
    "llm_do.toolsets.agent",
)
ALLOWED_EXACT_IMPORTS = {
    "llm_do.toolsets.approval",
}


def _module_name_for_file(path: Path) -> str:
    return "llm_do.runtime." + ".".join(path.relative_to(RUNTIME_DIR).with_suffix("").parts)


def _resolve_from_import(
    *,
    module_name: str,
    imported_module: str | None,
    level: int,
) -> str:
    module_parts = module_name.split(".")
    parent_parts = module_parts[:-level]
    if imported_module:
        return ".".join((*parent_parts, *imported_module.split(".")))
    return ".".join(parent_parts)


def _is_forbidden(module: str) -> bool:
    if module in ALLOWED_EXACT_IMPORTS:
        return False
    return any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in FORBIDDEN_PREFIXES
    )


def test_runtime_dependency_direction() -> None:
    violations: list[str] = []
    for file_path in sorted(RUNTIME_DIR.rglob("*.py")):
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        module_name = _module_name_for_file(file_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    if _is_forbidden(imported):
                        violations.append(
                            f"{file_path}:{node.lineno} imports forbidden module {imported!r}"
                        )
            elif isinstance(node, ast.ImportFrom):
                imported = _resolve_from_import(
                    module_name=module_name,
                    imported_module=node.module,
                    level=node.level,
                )
                if _is_forbidden(imported):
                    violations.append(
                        f"{file_path}:{node.lineno} imports forbidden module {imported!r}"
                    )

    assert not violations, "Runtime dependency violations:\n" + "\n".join(violations)
