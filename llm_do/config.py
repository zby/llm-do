"""Configuration loading for llm-do.

Reads optional TOML config files from the working directory to control
model requirements, spec sources, and other workflow settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - fallback for <3.11
    import tomli as tomllib


CONFIG_FILENAMES = ("llm-do.toml",)


@dataclass
class ModelConstraints:
    allowed_models: List[str] = field(default_factory=list)
    required_attachment_types: List[str] = field(default_factory=list)


@dataclass
class PromptSettings:
    template: Optional[str] = None
    params: Dict[str, str] = field(default_factory=dict)


@dataclass
class WorkflowSettings:
    spec_file: Optional[str] = None


@dataclass
class LlmDoConfig:
    model: ModelConstraints = field(default_factory=ModelConstraints)
    prompt: PromptSettings = field(default_factory=PromptSettings)
    workflow: WorkflowSettings = field(default_factory=WorkflowSettings)
    path: Optional[Path] = None

    @property
    def requires_attachment_types(self) -> List[str]:
        return self.model.required_attachment_types


def load_config(base_dir: Path) -> LlmDoConfig:
    """Load config from the first matching file in the working directory."""

    for filename in CONFIG_FILENAMES:
        candidate = base_dir / filename
        if not candidate.exists():
            continue
        with candidate.open("rb") as f:
            data = tomllib.load(f)
        return LlmDoConfig(
            model=_parse_model(data.get("model", {})),
            prompt=_parse_prompt(data.get("prompt", {})),
            workflow=_parse_workflow(data.get("workflow", {})),
            path=candidate,
        )

    return LlmDoConfig()


def _parse_model(raw: dict) -> ModelConstraints:
    allowed = raw.get("allowed_models") or []
    required = raw.get("required_attachment_types") or []
    return ModelConstraints(
        allowed_models=list(allowed),
        required_attachment_types=list(required),
    )


def _parse_prompt(raw: dict) -> PromptSettings:
    template = raw.get("template")
    params = raw.get("params") or {}
    return PromptSettings(template=template, params=dict(params))


def _parse_workflow(raw: dict) -> WorkflowSettings:
    spec_file = raw.get("spec")
    return WorkflowSettings(spec_file=spec_file)
