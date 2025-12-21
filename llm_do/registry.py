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

# Generated workers go to a temp directory, not workshop directory.
# This keeps generated workers ephemeral - use `cp` to persist them.
GENERATED_DIR = Path("/tmp/llm-do/generated")

import frontmatter
import yaml
from jinja2 import (
    Environment,
    FileSystemLoader,
    ChoiceLoader,
    StrictUndefined,
    TemplateError,
)
from pydantic import BaseModel, ValidationError

from .types import OutputSchemaResolver, WorkerDefinition


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

    Provides a `file(path)` function that loads files from template roots.
    Also supports standard {% include %} directive with the same search paths.

    Template search order (applies to both file() and include):
    1. Worker directory (for directory-form workers)
    2. Program templates/ directory
    3. Built-in templates

    Uses StrictUndefined so missing template variables raise errors immediately
    instead of silently rendering as empty strings.

    Args:
        template_str: Jinja2 template string
        template_roots: List of directories to search for templates (in order)

    Returns:
        Rendered template string

    Raises:
        FileNotFoundError: If a referenced file doesn't exist
        PermissionError: If a file path escapes allowed directories
        ValueError: Wraps Jinja2 TemplateError (syntax errors, undefined vars, etc.)
    """
    loader = _build_template_loader(template_roots)

    # Build the full search path including built-ins (for file() function)
    builtin_templates = Path(__file__).parent / "templates"
    all_roots = list(template_roots)
    if builtin_templates.exists():
        all_roots.append(builtin_templates)

    env = Environment(
        loader=loader,
        autoescape=False,  # Don't escape - we want raw text
        keep_trailing_newline=True,
        undefined=StrictUndefined,  # Fail fast on missing variables
    )

    # Add custom file() function that searches all template roots including built-ins
    def load_file(path_str: str) -> str:
        """Load a file from template roots (including built-ins)."""
        # Try each root in order
        for root in all_roots:
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
    except TemplateError as exc:
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
        # Cache for loaded definitions (used by CLI for override injection)
        self._definitions_cache: Dict[str, WorkerDefinition] = {}

    # paths -----------------------------------------------------------------
    def _get_search_paths(self, name: str) -> list[Path]:
        """Get candidate paths to search for a worker.

        Handles multiple name formats:
        - Library references: "lib:worker" (Phase 3)
        - Explicit relative paths: "./path/to/worker"
        - Plain worker names: searched at registry root

        Search order for plain names:
        1. Simple form at root: {root}/{name}.worker
        2. Directory form at root: {root}/{name}/worker.worker
        3. Generated workers (this session only)
        4. Built-in workers

        Args:
            name: Worker name, path, or reference

        Returns:
            List of candidate paths to check

        Raises:
            ValueError: If name uses unsupported syntax (e.g., "../")
        """
        # Names are expected to come from trusted config; guardrails here avoid accidental escapes.
        # Library references (lib:worker) not yet supported
        # Skip Windows drive letters like "C:\" and absolute paths
        if ":" in name and not name.startswith("/") and not (len(name) > 1 and name[1] == ":"):
            raise ValueError(f"Library references ('{name}') not yet supported.")

        # Handle explicit relative paths: "./path/to/worker"
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

        # Plain worker name - search at registry root
        candidates = [
            # Simple form: {root}/{name}.worker
            self.root / f"{name}.worker",
            # Directory form: {root}/{name}/worker.worker
            self.root / name / "worker.worker",
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

    def resolve_worker_path(self, name: str) -> Path:
        """Return the resolved path for an existing worker definition."""
        path = self._definition_path(name)
        if not path.exists():
            raise FileNotFoundError(f"Worker definition not found: {name}")
        return path

    def _get_template_roots(self, worker_path: Path) -> list[Path]:
        """Build list of template search paths for a worker.

        Search order:
        1. Worker directory templates/ subdirectory (if exists)
        2. Worker directory itself (for local includes)
        3. Built-in templates (added by _render_jinja_template)

        Args:
            worker_path: Path to the worker file

        Returns:
            List of template root directories to search
        """
        roots = []

        # Worker's own directory (for directory-form workers with local templates)
        worker_dir = worker_path.parent
        if (worker_dir / "templates").exists():
            roots.append(worker_dir / "templates")
        roots.append(worker_dir)  # Also allow includes relative to worker

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
        1. Worker directory: {root}/{name}/tools.py (for directory-form workers)
        2. Registry root: {root}/tools.py (for simple-form workers)

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

        # 2. Check registry root (for simple-form workers)
        root_tools = self.root / "tools.py"
        if root_tools.exists():
            return root_tools

        return None

    def register_generated(self, name: str) -> None:
        """Register a worker as generated in this session.

        Only workers registered here will be findable via load_definition.
        This prevents leakage from old sessions in the shared /tmp directory.
        """
        self._generated_workers.add(name)

    def is_generated(self, name: str) -> bool:
        """Return True if worker was generated in this session."""
        return name in self._generated_workers

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

    def list_workers(self) -> list[str]:
        """List all available worker names.

        Scans registry root, built-ins, and generated workers from this session.

        Returns:
            List of worker names (without path or .worker suffix)
        """
        workers: set[str] = set()

        # Scan registry root for workers
        # Simple form: {root}/{name}.worker
        for path in self.root.glob("*.worker"):
            workers.add(path.stem)
        # Directory form: {root}/{name}/worker.worker
        for path in self.root.glob("*/worker.worker"):
            workers.add(path.parent.name)

        # Include generated workers from this session
        workers.update(self._generated_workers)

        # Scan built-in workers
        builtin_dir = Path(__file__).parent / "workers"
        if builtin_dir.exists():
            for path in builtin_dir.glob("*.worker"):
                workers.add(path.stem)
            for path in builtin_dir.glob("*/worker.worker"):
                workers.add(path.parent.name)

        return sorted(workers)

    def load_definition(self, name: str) -> WorkerDefinition:
        """Load a worker definition by name.

        Searches in order:
        1. Direct file path (if name points to an existing file)
        2. {root}/{name}.worker (simple form at root)
        3. {root}/{name}/worker.worker (directory form at root)
        4. /tmp/llm-do/generated/{name}/worker.worker (only if generated in this session)
        5. Built-in workers (llm_do/workers/{name}.worker or llm_do/workers/{name}/worker.worker)

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
        # Check cache first (used for CLI override injection)
        if name in self._definitions_cache:
            return self._definitions_cache[name]

        if name.startswith("../"):
            raise ValueError(
                "Parent directory references ('..') are not allowed in worker names. "
                "Use library references (lib:worker) for cross-project dependencies."
            )

        def load_from_path(path: Path) -> WorkerDefinition:
            data = self._load_raw(path)
            try:
                definition = WorkerDefinition.model_validate(data)
            except ValidationError as exc:
                raise ValueError(f"Invalid worker definition at {path}: {exc}") from exc
            return definition

        # Allow direct file paths when they exist (absolute or relative).
        direct = Path(name).expanduser()
        candidates = [direct]
        if not direct.is_absolute():
            candidates.append(self.root / direct)
        for candidate in candidates:
            if candidate.is_file():
                return load_from_path(candidate)

        path = self._definition_path(name)
        if not path.exists():
            # _definition_path returns the first candidate if none exist,
            # but we want to be sure we checked all of them in the error message
            raise FileNotFoundError(f"Worker definition not found: {name}")
        return load_from_path(path)

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
        self._definitions_cache.pop(definition.name, None)
        return target

    def resolve_output_schema(self, definition: WorkerDefinition) -> Optional[Type[BaseModel]]:
        """Resolve the output schema for a worker definition.

        Uses the configured output_schema_resolver callback.
        """
        return self.output_schema_resolver(definition)
