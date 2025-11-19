"""Sandboxed file toolbox for llm templates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Union

import llm


@dataclass
class Sandbox:
    """Represents a sandboxed directory."""

    root: Path
    read_only: bool

    def resolve(self, relative: str) -> Path:
        """Resolve a relative path within the sandbox."""
        relative = relative.lstrip("/")
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Path escapes sandbox") from exc
        return candidate


class Files(llm.Toolbox):
    """Expose read/write helpers inside a sandboxed directory."""

    name = "Files"

    def __init__(self, config: Union[str, dict]):
        alias_override = None
        if isinstance(config, str):
            if ":" not in config:
                raise ValueError(
                    "Files toolbox requires config in the form '<mode>:<path>'"
                )
            mode, path = config.split(":", 1)
        elif isinstance(config, dict):
            mode = config.get("mode", "ro")
            path = config.get("path")
            alias_override = config.get("alias")
            if not path:
                raise ValueError("Files toolbox requires a 'path'")
        else:
            raise TypeError("Files config must be a string or dict")
        mode = str(mode).strip().lower()
        if mode not in {"ro", "out"}:
            raise ValueError("Files toolbox mode must be 'ro' or 'out'")
        resolved = Path(str(path)).expanduser().resolve()
        if not resolved.exists():
            if mode == "ro":
                raise ValueError(f"Sandbox path does not exist: {resolved}")
            resolved.mkdir(parents=True, exist_ok=True)
        if not resolved.is_dir():
            raise ValueError("Sandbox path must be a directory")
        self.sandbox = Sandbox(root=resolved, read_only=(mode == "ro"))
        alias_value = alias_override or self._alias_from_path(resolved, mode)
        self.alias = re.sub(r"[^a-z0-9_]+", "_", alias_value.lower())
        self._tool_prefix = f"{self.__class__.__name__}_{self.alias}"

    # tool methods -----------------------------------------------------
    def list(self, pattern: str = "**/*") -> List[str]:
        """List files relative to the sandbox root using glob pattern."""
        pattern = pattern or "**/*"
        matches: List[str] = []
        for path in self.sandbox.root.glob(pattern):
            try:
                rel = path.relative_to(self.sandbox.root)
            except ValueError:
                continue
            matches.append(str(rel))
        return sorted(matches)

    def read_text(self, path: str, max_chars: int = 200_000) -> str:
        """Read a UTF-8 text file inside the sandbox."""
        if max_chars <= 0:
            raise ValueError("max_chars must be positive")
        target = self._file_for_read(path)
        content = target.read_text(encoding="utf-8")
        if len(content) > max_chars:
            raise ValueError(
                f"File exceeds max_chars ({len(content)} > {max_chars})"
            )
        return content

    def write_text(self, path: str, content: str) -> str:
        """Write text into the sandbox (disallowed for read-only sandboxes)."""
        if self.sandbox.read_only:
            raise PermissionError("Sandbox is read-only")
        target = self._file_for_write(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        rel = target.relative_to(self.sandbox.root)
        return f"wrote {len(content)} chars to {rel}"

    # internal helpers -------------------------------------------------
    def _file_for_read(self, path: str) -> Path:
        target = self.sandbox.resolve(path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(path)
        return target

    def _file_for_write(self, path: str) -> Path:
        if not path:
            raise ValueError("Path is required")
        return self.sandbox.resolve(path)

    # toolbox wiring ---------------------------------------------------
    def tools(self):
        """Expose sandbox methods with per-instance prefixes."""
        for attr in ("list", "read_text", "write_text"):
            method = getattr(self, attr)
            yield llm.Tool.function(
                method, name=f"{self._tool_prefix}_{attr}"
            )
        yield from self._extra_tools

    @staticmethod
    def _alias_from_path(path: Path, mode: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", path.name.lower()).strip("_")
        return f"{slug or 'sandbox'}_{mode}"


__all__: Iterable[str] = ["Files"]
