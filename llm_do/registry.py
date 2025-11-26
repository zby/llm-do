"""Worker registry for loading and saving worker definitions.

This module provides the WorkerRegistry class which handles:
- Loading worker definitions from .worker files (YAML front matter + Jinja2 body)
- Searching for workers in multiple locations (workers/, /tmp/llm-do/generated/, built-in)
- Rendering Jinja2 templates in worker instructions
- Saving worker definitions with locking support
"""
from __future__ import annotations

import os
from pathlib import Path

# Generated workers go to a temp directory, not project directory.
# This keeps generated workers ephemeral - use `cp` to persist them.
GENERATED_DIR = Path("/tmp/llm-do/generated")
from typing import Dict, Optional, Set, Type

import frontmatter
import yaml
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, UndefinedError
from pydantic import BaseModel, ValidationError

from .types import OutputSchemaResolver, WorkerDefinition


def _default_resolver(definition: WorkerDefinition) -> Optional[Type[BaseModel]]:
    """Default output schema resolver that returns None."""
    return None


def _render_jinja_template(template_str: str, template_root: Path) -> str:
    """Render a Jinja2 template with worker directory as the base.

    Provides a `file(path)` function that loads files relative to template_root.
    Also supports standard {% include %} directive.

    Args:
        template_str: Jinja2 template string
        template_root: Root directory for template file loading (worker's directory)

    Returns:
        Rendered template string

    Raises:
        FileNotFoundError: If a referenced file doesn't exist
        PermissionError: If a file path escapes template root directory
        jinja2.TemplateError: If template syntax is invalid
    """
    # Set up Jinja2 environment with worker directory as base
    env = Environment(
        loader=FileSystemLoader(template_root),
        autoescape=False,  # Don't escape - we want raw text
        keep_trailing_newline=True,
    )

    # Add custom file() function
    def load_file(path_str: str) -> str:
        """Load a file relative to template root."""
        file_path = (template_root / path_str).resolve()

        # Security: ensure resolved path doesn't escape template root
        try:
            file_path.relative_to(template_root)
        except ValueError:
            raise PermissionError(
                f"File path escapes allowed directory: {path_str}"
            )

        if not file_path.exists():
            raise FileNotFoundError(
                f"File not found: {path_str}"
            )

        return file_path.read_text(encoding="utf-8")

    # Make file() available in templates
    env.globals["file"] = load_file

    # Render the template
    try:
        template = env.from_string(template_str)
        return template.render()
    except (TemplateNotFound, UndefinedError) as exc:
        raise ValueError(f"Template error: {exc}") from exc


def _has_jinja_syntax(text: str) -> bool:
    """Check if text contains Jinja2 template syntax."""
    return "{{" in text or "{%" in text or "{#" in text


class WorkerRegistry:
    """File-backed registry for worker artifacts."""

    def __init__(
        self,
        root: Path,
        *,
        output_schema_resolver: OutputSchemaResolver = _default_resolver,
        generated_dir: Optional[Path] = None,
    ):
        self.root = Path(root).expanduser().resolve()
        self.output_schema_resolver = output_schema_resolver
        self.root.mkdir(parents=True, exist_ok=True)
        # Generated workers directory - defaults to /tmp/llm-do/generated
        # Can be overridden for tests
        self.generated_dir = Path(generated_dir) if generated_dir else GENERATED_DIR
        # Track workers generated in this session - only these are searchable
        self._generated_workers: Set[str] = set()

    # paths -----------------------------------------------------------------
    def _get_search_paths(self, name: str) -> list[Path]:
        base = Path(name)
        if base.suffix:
            return [base if base.is_absolute() else (self.root / base)]

        candidates = [
            # Simple form: workers/name.worker
            self.root / "workers" / f"{name}.worker",
            # Directory form: workers/name/worker.worker
            self.root / "workers" / name / "worker.worker",
        ]

        # Only include generated path if this worker was generated in this session
        # Generated workers are always directories: {generated_dir}/{name}/worker.worker
        if name in self._generated_workers:
            candidates.append(self.generated_dir / name / "worker.worker")

        # Add built-in paths (both forms)
        builtin_simple = Path(__file__).parent / "workers" / f"{name}.worker"
        builtin_dir = Path(__file__).parent / "workers" / name / "worker.worker"
        candidates.extend([builtin_simple, builtin_dir])

        return candidates

    def _definition_path(self, name: str) -> Path:
        # Legacy helper: return the first existing path, or the default user path
        paths = self._get_search_paths(name)
        for path in paths:
            if path.exists():
                return path
        return paths[0]  # Default to workers/{name}.worker

    def _load_raw(self, path: Path) -> Dict[str, any]:
        """Load worker definition from .worker file with front matter."""
        suffix = path.suffix.lower()
        if suffix != ".worker":
            raise ValueError(
                f"Worker definition must be .worker, got: {suffix}"
            )

        content = path.read_text(encoding="utf-8")
        post = frontmatter.loads(content)

        # Front matter becomes the data dict
        data = dict(post.metadata)

        # Body (if present) becomes instructions
        # Render Jinja2 if the body contains template syntax
        if post.content.strip():
            body = post.content
            if _has_jinja_syntax(body):
                # Render using worker's directory as template root
                template_root = path.parent
                rendered = _render_jinja_template(body, template_root)
                data["instructions"] = rendered
            else:
                data["instructions"] = body

        return data

    def find_custom_tools(self, name: str) -> Optional[Path]:
        """Find custom tools module for a worker.

        Checks for tools.py in the same directory as the worker definition.
        Only applies to directory-based workers (workers/name/worker.worker).

        Args:
            name: Worker name

        Returns:
            Path to tools.py if it exists, None otherwise
        """
        path = self._definition_path(name)
        if not path.exists():
            return None

        # Only directory-based workers can have custom tools
        # Check if this is workers/name/worker.worker pattern
        if path.name == "worker.worker":
            tools_path = path.parent / "tools.py"
            if tools_path.exists():
                return tools_path

        return None

    def register_generated(self, name: str) -> None:
        """Register a worker as generated in this session.

        Only workers registered here will be findable via load_definition.
        This prevents leakage from old sessions in the shared /tmp directory.
        """
        self._generated_workers.add(name)

    def worker_exists(self, name: str) -> bool:
        """Check if a worker with this name exists anywhere.

        Used for conflict detection before creating new workers.
        Checks project workers, built-ins, AND generated dir (even from old sessions).
        """
        for path in self._get_search_paths(name):
            if path.exists():
                return True
        # Also check generated dir unconditionally (prevent overwriting old sessions)
        # Generated workers are directories: {generated_dir}/{name}/worker.worker
        if (self.generated_dir / name / "worker.worker").exists():
            return True
        return False

    def load_definition(self, name: str) -> WorkerDefinition:
        """Load a worker definition by name.

        Searches in order:
        1. {root}/workers/{name}.worker
        2. {root}/workers/{name}/worker.worker (directory form)
        3. /tmp/llm-do/generated/{name}.worker (only if generated in this session)
        4. Built-in workers (llm_do/workers/{name}.worker or llm_do/workers/{name}/worker.worker)

        Note: Generated workers from /tmp are only found if they were created
        in this session via register_generated(). This prevents leakage from
        old sessions.

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
        """Save a worker definition to disk as .worker file with front matter.

        Args:
            definition: WorkerDefinition to save
            force: If True, overwrite locked workers
            path: Optional custom path (defaults to workers/{name}.worker)

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

        # Extract instructions for body
        data_dict = definition.model_dump(exclude_none=True, mode="json")
        instructions = data_dict.pop("instructions", None)

        # Create front matter post
        post = frontmatter.Post(
            content=instructions or "",
            **data_dict
        )

        # Serialize to .worker format
        serialized = frontmatter.dumps(post)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(serialized, encoding="utf-8")
        return target

    def resolve_output_schema(self, definition: WorkerDefinition) -> Optional[Type[BaseModel]]:
        """Resolve the output schema for a worker definition.

        Uses the configured output_schema_resolver callback.
        """
        return self.output_schema_resolver(definition)
