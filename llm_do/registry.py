"""Worker registry for loading and saving worker definitions.

This module provides the WorkerRegistry class which handles:
- Loading worker definitions from YAML files
- Searching for workers in multiple locations (workers/, workers/generated/, built-in)
- Resolving prompts from prompts/ directory
- Saving worker definitions with locking support
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Type

import yaml
from pydantic import BaseModel, ValidationError

from . import prompts
from .types import OutputSchemaResolver, WorkerDefinition


def _default_resolver(definition: WorkerDefinition) -> Optional[Type[BaseModel]]:
    """Default output schema resolver that returns None."""
    return None


class WorkerRegistry:
    """File-backed registry for worker artifacts."""

    def __init__(
        self,
        root: Path,
        *,
        output_schema_resolver: OutputSchemaResolver = _default_resolver,
    ):
        self.root = Path(root).expanduser().resolve()
        self.output_schema_resolver = output_schema_resolver
        self.root.mkdir(parents=True, exist_ok=True)

    # paths -----------------------------------------------------------------
    def _get_search_paths(self, name: str) -> list[Path]:
        base = Path(name)
        if base.suffix:
            return [base if base.is_absolute() else (self.root / base)]

        candidates = [
            # Simple form: workers/name.yaml
            self.root / "workers" / f"{name}.yaml",
            # Directory form: workers/name/worker.yaml
            self.root / "workers" / name / "worker.yaml",
            # Generated simple form
            self.root / "workers" / "generated" / f"{name}.yaml",
        ]

        # Add built-in paths (both forms)
        builtin_simple = Path(__file__).parent / "workers" / f"{name}.yaml"
        builtin_dir = Path(__file__).parent / "workers" / name / "worker.yaml"
        candidates.extend([builtin_simple, builtin_dir])

        return candidates

    def _definition_path(self, name: str) -> Path:
        # Legacy helper: return the first existing path, or the default user path
        paths = self._get_search_paths(name)
        for path in paths:
            if path.exists():
                return path
        return paths[0]  # Default to workers/{name}.yaml

    def _load_raw(self, path: Path) -> Dict[str, any]:
        suffix = path.suffix.lower()
        if suffix not in {".yaml", ".yml"}:
            raise ValueError(
                f"Worker definition must be .yaml or .yml, got: {suffix}"
            )
        content = path.read_text(encoding="utf-8")
        return yaml.safe_load(content) or {}

    def find_custom_tools(self, name: str) -> Optional[Path]:
        """Find custom tools module for a worker.

        Checks for tools.py in the same directory as the worker definition.
        Only applies to directory-based workers (workers/name/worker.yaml).

        Args:
            name: Worker name

        Returns:
            Path to tools.py if it exists, None otherwise
        """
        path = self._definition_path(name)
        if not path.exists():
            return None

        # Only directory-based workers can have custom tools
        # Check if this is workers/name/worker.yaml pattern
        if path.name == "worker.yaml":
            tools_path = path.parent / "tools.py"
            if tools_path.exists():
                return tools_path

        return None

    def load_definition(self, name: str) -> WorkerDefinition:
        """Load a worker definition by name.

        Searches in order:
        1. {root}/workers/{name}.yaml
        2. {root}/workers/{name}/worker.yaml (directory form)
        3. {root}/workers/generated/{name}.yaml
        4. Built-in workers (llm_do/workers/{name}.yaml or llm_do/workers/{name}/worker.yaml)

        Args:
            name: Worker name to load

        Returns:
            Loaded and validated WorkerDefinition

        Raises:
            FileNotFoundError: If worker not found in any location
            ValueError: If worker definition is invalid
        """
        path = self._definition_path(name)
        if not path.exists():
            # _definition_path returns the first candidate if none exist,
            # but we want to be sure we checked all of them in the error message
            raise FileNotFoundError(f"Worker definition not found: {name}")
        data = self._load_raw(path)

        # Determine project root: workers stored under project/workers/** should inherit
        # the project root directory so prompts/ resolves correctly.
        project_root = path.parent
        resolved_path = path.resolve()
        user_workers_dir = (self.root / "workers").resolve()
        if resolved_path.is_relative_to(user_workers_dir):
            project_root = user_workers_dir.parent

        prompts_dir = project_root / "prompts"
        worker_name = data.get("name", name)

        resolved_instructions = prompts.resolve_worker_instructions(
            raw_instructions=data.get("instructions"),
            worker_name=worker_name,
            prompts_dir=prompts_dir,
        )

        if resolved_instructions is not None:
            data["instructions"] = resolved_instructions

        # Inject sandbox names from dictionary keys
        if "sandboxes" in data and isinstance(data["sandboxes"], dict):
            for sandbox_name, sandbox_config in data["sandboxes"].items():
                if isinstance(sandbox_config, dict) and "name" not in sandbox_config:
                    sandbox_config["name"] = sandbox_name

        # Inject tool rule names from dictionary keys
        if "tool_rules" in data and isinstance(data["tool_rules"], dict):
            for rule_name, rule_config in data["tool_rules"].items():
                if isinstance(rule_config, dict) and "name" not in rule_config:
                    rule_config["name"] = rule_name

        try:
            return WorkerDefinition.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Invalid worker definition at {path}: {exc}") from exc

    def save_definition(
        self,
        definition: WorkerDefinition,
        *,
        force: bool = False,
        path: Optional[Path] = None,
    ) -> Path:
        """Save a worker definition to disk.

        Args:
            definition: WorkerDefinition to save
            force: If True, overwrite locked workers
            path: Optional custom path (defaults to workers/{name}.yaml)

        Returns:
            Path where the definition was saved

        Raises:
            PermissionError: If trying to overwrite locked worker without force
        """
        target = path or self._definition_path(definition.name)
        if target.exists() and definition.locked and not force:
            raise PermissionError("Cannot overwrite locked worker without force=True")
        if target.exists() and not force:
            existing = self.load_definition(str(target))
            if existing.locked:
                raise PermissionError(
                    "Existing worker is locked; pass force=True to overwrite"
                )
        serialized = yaml.safe_dump(
            definition.model_dump(exclude_none=True, mode="json")
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(serialized, encoding="utf-8")
        return target

    def resolve_output_schema(self, definition: WorkerDefinition) -> Optional[Type[BaseModel]]:
        """Resolve the output schema for a worker definition.

        Uses the configured output_schema_resolver callback.
        """
        return self.output_schema_resolver(definition)
