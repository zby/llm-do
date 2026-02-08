"""Project/linker APIs for manifest-driven runtime wiring."""

from .agent_file import (
    AgentDefinition,
    AgentFileParser,
    load_agent_file,
    load_agent_file_parts,
    parse_agent_file,
)
from .discovery import (
    discover_agents_from_module,
    discover_tools_from_module,
    discover_toolsets_from_module,
    load_agents_from_files,
    load_all_from_files,
    load_module,
    load_tools_from_files,
    load_toolsets_from_files,
)
from .entry_resolver import resolve_entry
from .host_toolsets import (
    RegistryHostWiring,
    build_agent_toolset_factory,
    build_host_toolsets,
    build_registry_host_wiring,
)
from .manifest import (
    EntryConfig,
    ManifestRuntimeConfig,
    ProjectManifest,
    load_manifest,
    resolve_generated_agents_dir,
    resolve_manifest_paths,
)
from .registry import AgentRegistry, AgentToolsetFactory, build_registry
from .tool_resolution import resolve_tool_defs, resolve_toolset_defs

__all__ = [
    "AgentDefinition",
    "AgentFileParser",
    "load_agent_file",
    "load_agent_file_parts",
    "parse_agent_file",
    "discover_agents_from_module",
    "discover_tools_from_module",
    "discover_toolsets_from_module",
    "load_agents_from_files",
    "load_all_from_files",
    "load_module",
    "load_tools_from_files",
    "load_toolsets_from_files",
    "resolve_entry",
    "ProjectManifest",
    "ManifestRuntimeConfig",
    "EntryConfig",
    "load_manifest",
    "resolve_generated_agents_dir",
    "resolve_manifest_paths",
    "build_host_toolsets",
    "build_agent_toolset_factory",
    "build_registry_host_wiring",
    "RegistryHostWiring",
    "AgentRegistry",
    "AgentToolsetFactory",
    "build_registry",
    "resolve_tool_defs",
    "resolve_toolset_defs",
]
