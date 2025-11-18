"""Workflow execution context used by llm-do."""

from __future__ import annotations

import click
import llm
from pathlib import Path
from typing import Optional, Tuple

from .config import LlmDoConfig, load_config
from .toolbox import BaseToolbox


class WorkflowContext:
    """Encapsulates workflow configuration, spec, and toolbox state."""

    def __init__(
        self,
        working_dir: Path,
        *,
        spec_path: Optional[str] = None,
        toolbox=None,
    ) -> None:
        self.working_dir = Path(working_dir)
        self.config = load_config(self.working_dir)
        self.spec_path = self._resolve_spec_path(spec_path)
        self.toolbox = toolbox or BaseToolbox(working_dir=self.working_dir)
        self._spec_cache: Optional[str] = None

    @property
    def spec_text(self) -> str:
        if self._spec_cache is None:
            self._spec_cache = self.spec_path.read_text()
        return self._spec_cache

    def build_prompt(self, task: str) -> Tuple[str, str]:
        """Return prompt/system strings, applying template if configured."""

        prompt_text = task
        system_text = self.spec_text

        template_name = self.config.prompt.template
        if not template_name:
            return prompt_text, system_text

        from llm.cli import LoadTemplateError, load_template
        from llm.templates import Template

        try:
            template = load_template(template_name)
        except LoadTemplateError as exc:
            raise Exception(f"Unable to load template '{template_name}': {exc}")

        params = dict(self.config.prompt.params)
        params.setdefault("spec", system_text)
        params.setdefault("spec_path", str(self.spec_path))
        params.setdefault("task", task)
        params.setdefault("working_dir", str(self.working_dir))

        try:
            template_prompt, template_system = template.evaluate(task, params)
        except Template.MissingVariables as exc:
            raise Exception(
                f"Template '{template_name}' is missing variables: {exc}"
            )

        if template_prompt:
            prompt_text = template_prompt
        if template_system:
            system_text = template_system

        return prompt_text, system_text

    def resolve_model_name(self, override: Optional[str]) -> str:
        return override or llm.get_default_model()

    def ensure_model_allowed(self, model, resolved_name: str) -> None:
        allowed = set(self.config.model.allowed_models)
        if allowed:
            candidate_names = {resolved_name, getattr(model, "model_id", resolved_name)}
            model_name = getattr(model, "model_name", None)
            if model_name:
                candidate_names.add(model_name)
            if candidate_names.isdisjoint(allowed):
                raise Exception(
                    "Model '{}' is not permitted for this workflow. Allowed models: {}".format(
                        resolved_name,
                        ", ".join(sorted(allowed)),
                    )
                )

        required_types = set(self.config.requires_attachment_types)
        if required_types:
            supported = set(getattr(model, "attachment_types", set()))
            missing = sorted(required_types - supported)
            if missing:
                raise Exception(
                    "Model '{}' is missing required attachment support: {}".format(
                        resolved_name, ", ".join(missing)
                    )
                )

    def _resolve_spec_path(self, override: Optional[str]) -> Path:
        if override:
            return self._validate_spec_path(Path(override))

        if not self.config.path:
            raise click.ClickException(
                f"No llm-do config found in {self.working_dir}. Provide --spec or create llm-do.toml with workflow.spec."
            )
        if not self.config.workflow.spec_file:
            raise click.ClickException(
                f"Config {self.config.path} is missing [workflow].spec. Provide --spec or set it there."
            )

        return self._validate_spec_path(self.working_dir / self.config.workflow.spec_file)

    def _validate_spec_path(self, candidate: Path) -> Path:
        if candidate.exists():
            return candidate.resolve()

        if not candidate.is_absolute():
            alt = (self.working_dir / candidate).resolve()
            if alt.exists():
                return alt

        raise click.ClickException(f"Spec file not found: {candidate}")
