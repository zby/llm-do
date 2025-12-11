"""Worker registry for loading and saving worker definitions.

This module provides the WorkerRegistry class which handles:
- Loading worker definitions from .worker files (YAML front matter + Jinja2 body)
- Searching for workers in multiple locations (workers/, /tmp/llm-do/generated/, built-in)
- Rendering Jinja2 templates in worker instructions
- Saving worker definitions with locking support
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Set, Type

# Generated workers go to a temp directory, not program directory.
# This keeps generated workers ephemeral - use `cp` to persist them.
GENERATED_DIR = Path("/tmp/llm-do/generated")

import frontmatter
import yaml
from jinja2 import Environment, FileSystemLoader, ChoiceLoader, TemplateNotFound, UndefinedError
from pydantic import BaseModel, ValidationError

from .types import OutputSchemaResolver, ProgramConfig, WorkerDefinition


def _default_resolver(definition: WorkerDefinition) -> Optional[Type[BaseModel]]:
    """Default output schema resolver that returns None."""
    return None


def _build_template_loader(template_roots: list[Path]) -> ChoiceLoader:
    """Build a Jinja2 loader with multiple search paths.

    Args:
        template_roots: List of directories to search for templates (in order)

    Returns:
        ChoiceLoader that searches all paths in order
    """
    loaders = []

    # Add file system loaders for each root that exists
    for root in template_roots:
        if root.exists():
            loaders.append(FileSystemLoader(root))

    # Add built-in templates
    builtin_templates = Path(__file__).parent / "templates"
    if builtin_templates.exists():
        loaders.append(FileSystemLoader(builtin_templates))

    return ChoiceLoader(loaders) if loaders else FileSystemLoader(".")


def _render_jinja_template(template_str: str, template_roots: list[Path]) -> str:
    """Render a Jinja2 template with multiple search paths.

    Provides a `file(path)` function that loads files relative to the first template root.
    Also supports standard {% include %} directive with multiple search paths.

    Template search order:
    1. Worker directory (for directory-form workers)
    2. Program templates/ directory
    3. Built-in templates

    Args:
        template_str: Jinja2 template string
        template_roots: List of directories to search for templates (in order)

    Returns:
        Rendered template string

    Raises:
        FileNotFoundError: If a referenced file doesn't exist
        PermissionError: If a file path escapes allowed directories
        jinja2.TemplateError: If template syntax is invalid
    """
    loader = _build_template_loader(template_roots)

    env = Environment(
        loader=loader,
        autoescape=False,  # Don't escape - we want raw text
        keep_trailing_newline=True,
    )

    # Add custom file() function that searches all template roots
    def load_file(path_str: str) -> str:
        """Load a file relative to template roots."""
        # Try each root in order
        for root in template_roots:
            file_path = (root / path_str).resolve()

            # Security: ensure resolved path doesn't escape this root
            try:
                file_path.relative_to(root)
            except ValueError:
                continue  # Try next root

            if file_path.exists():
                return file_path.read_text(encoding="utf-8")

        raise FileNotFoundError(f"File not found in any template root: {path_str}")

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
        program_config: Optional[ProgramConfig] = None,
    ):
        self.root = Path(root).expanduser().resolve()
        self.output_schema_resolver = output_schema_resolver
        self.root.mkdir(parents=True, exist_ok=True)
        # Generated workers directory - defaults to /tmp/llm-do/generated
        # Can be overridden for tests
        self.generated_dir = Path(generated_dir) if generated_dir else GENERATED_DIR
        # Track workers generated in this session - only these are searchable
        self._generated_workers: Set[str] = set()
        # Program configuration for inheritance
        self.program_config = program_config
        # Cache for loaded definitions (used by CLI for override injection)
        self._definitions_cache: Dict[str, WorkerDefinition] = {}

    # paths -----------------------------------------------------------------
    def _get_search_paths(self, name: str) -> list[Path]:
        """Get candidate paths to search for a worker.

        Handles multiple name formats:
        - Absolute/relative file paths (with .worker suffix)
        - Library references: "lib:worker" (Phase 3)
        - Explicit relative paths: "./workers/helper"
        - Plain worker names: searched in standard locations

        Args:
            name: Worker name, path, or reference

        Returns:
            List of candidate paths to check

        Raises:
            ValueError: If name uses unsupported syntax (e.g., "../")
        """
        # Library references (lib:worker) not yet supported
        # Skip Windows drive letters like "C:\" and absolute paths
        if ":" in name and not name.startswith("/") and not (len(name) > 1 and name[1] == ":"):
            raise ValueError(f"Library references ('{name}') not yet supported.")

        # Handle explicit relative paths: "./workers/helper"
        if name.startswith("./"):
            rel_path = name[2:]  # Remove "./"
            # Try as worker name in the path
            candidates = [
                self.root / rel_path / "worker.worker",  # Directory form
                self.root / f"{rel_path}.worker",  # Simple form
            ]
            return candidates

        # Reject parent directory references
        if name.startswith("../"):
            raise ValueError(
                "Parent directory references ('..') are not allowed in worker names. "
                "Use library references (lib:worker) for cross-project dependencies."
            )

        # Handle file paths with suffix
        base = Path(name)
        if base.suffix:
            return [base if base.is_absolute() else (self.root / base)]

        # Plain worker name - search in standard locations
        candidates = []

        # Special case: "main" worker can be at project root
        if name == "main":
            candidates.append(self.root / "main.worker")

        # Standard locations in workers/
        candidates.extend([
            # Simple form: workers/name.worker
            self.root / "workers" / f"{name}.worker",
            # Directory form: workers/name/worker.worker
            self.root / "workers" / name / "worker.worker",
        ])

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

    def _get_template_roots(self, worker_path: Path) -> list[Path]:
        """Build list of template search paths for a worker.

        Search order:
        1. Worker directory (for directory-form workers)
        2. Program templates/ directory (if program_config is set)
        3. Built-in templates (added by _render_jinja_template)

        Args:
            worker_path: Path to the worker file

        Returns:
            List of template root directories to search
        """
        roots = []

        # 1. Worker's own directory (for directory-form workers with local templates)
        worker_dir = worker_path.parent
        if (worker_dir / "templates").exists():
            roots.append(worker_dir / "templates")
        roots.append(worker_dir)  # Also allow includes relative to worker

        # 2. Program templates directory
        if self.program_config is not None:
            program_templates = self.root / "templates"
            if program_templates.exists():
                roots.append(program_templates)

        return roots

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
                # Build template search paths
                template_roots = self._get_template_roots(path)
                rendered = _render_jinja_template(body, template_roots)
                data["instructions"] = rendered
            else:
                data["instructions"] = body

        return data

    def find_custom_tools(self, name: str) -> Optional[Path]:
        """Find custom tools module for a worker.

        Search order:
        1. Worker directory: workers/name/tools.py (for directory-form workers)
        2. Program root: tools.py (when program_config is set)

        Args:
            name: Worker name

        Returns:
            Path to tools.py if it exists, None otherwise
        """
        path = self._definition_path(name)
        if not path.exists():
            return None

        # 1. Check worker directory (for directory-form workers)
        if path.name == "worker.worker":
            tools_path = path.parent / "tools.py"
            if tools_path.exists():
                return tools_path

        # 2. Check program root (when in program mode)
        if self.program_config is not None:
            program_tools = self.root / "tools.py"
            if program_tools.exists():
                return program_tools

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

    def _apply_program_config(self, definition: WorkerDefinition) -> WorkerDefinition:
        """Apply program configuration inheritance to a worker definition.

        Merge rules (per spec):
        - Scalar values: worker overrides program
        - toolsets: deep merge (worker toolsets add to program toolsets)
        - sandbox.paths: deep merge (worker paths add to program paths)
        - Lists: worker replaces program (no merge)

        Args:
            definition: Worker definition to enhance

        Returns:
            WorkerDefinition with program defaults applied
        """
        if self.program_config is None:
            return definition

        # Start with worker's values
        updates = {}

        # Model: worker overrides program
        if definition.model is None and self.program_config.model is not None:
            updates["model"] = self.program_config.model

        # Toolsets: deep merge (program provides base, worker adds/overrides)
        if self.program_config.toolsets:
            merged_toolsets = dict(self.program_config.toolsets)
            if definition.toolsets:
                merged_toolsets.update(definition.toolsets)
            updates["toolsets"] = merged_toolsets
        elif definition.toolsets is None:
            # Worker has no toolsets and neither does program - keep as None
            pass

        # Sandbox: deep merge paths
        if self.program_config.sandbox:
            if definition.sandbox is None:
                updates["sandbox"] = self.program_config.sandbox.model_copy()
            else:
                # Merge sandbox paths
                merged_sandbox = definition.sandbox.model_copy()
                if self.program_config.sandbox.paths and merged_sandbox.paths:
                    # Worker paths override program paths with same name
                    merged_paths = dict(self.program_config.sandbox.paths)
                    merged_paths.update(merged_sandbox.paths)
                    merged_sandbox.paths = merged_paths
                elif self.program_config.sandbox.paths and not merged_sandbox.paths:
                    merged_sandbox.paths = dict(self.program_config.sandbox.paths)
                updates["sandbox"] = merged_sandbox

        if not updates:
            return definition

        # Create new definition with merged values
        return definition.model_copy(update=updates)

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

        If a program_config is set, program-level defaults are merged into
        the worker definition (worker values take precedence).

        Args:
            name: Worker name to load

        Returns:
            Loaded and validated WorkerDefinition

        Raises:
            FileNotFoundError: If worker not found in any location
            ValueError: If worker definition is invalid
        """
        # Check cache first (used for CLI override injection)
        if name in self._definitions_cache:
            return self._definitions_cache[name]

        path = self._definition_path(name)
        if not path.exists():
            # _definition_path returns the first candidate if none exist,
            # but we want to be sure we checked all of them in the error message
            raise FileNotFoundError(f"Worker definition not found: {name}")
        data = self._load_raw(path)

        try:
            definition = WorkerDefinition.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Invalid worker definition at {path}: {exc}") from exc

        # Apply program configuration inheritance
        return self._apply_program_config(definition)

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
