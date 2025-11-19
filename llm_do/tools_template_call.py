"""Toolbox that allows templates to call other templates."""

from __future__ import annotations

import fnmatch
import inspect
import json
import textwrap
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Iterable, List, Optional

import llm
from llm.templates import Template
from pydantic import BaseModel, ConfigDict, Field, field_validator


@lru_cache(maxsize=1)
def _llm_cli_module():
    """Import llm.cli lazily so plugin loading doesn't trigger circular imports."""

    from llm import cli as cli_module

    return cli_module


class TemplateCallConfig(BaseModel):
    allow_templates: List[str] = Field(default_factory=list)
    allowed_suffixes: List[str] = Field(default_factory=list)
    max_attachments: int = 4
    max_bytes: int = 10_000_000
    ignore_functions: bool = True
    lock_template: Optional[str] = None
    default_model: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("allowed_suffixes")
    @classmethod
    def _lower_suffixes(cls, values: List[str]) -> List[str]:
        return [str(value).lower() for value in values]

    @field_validator("max_attachments")
    @classmethod
    def _validate_max_attachments(cls, value: int) -> int:
        if value < 0:
            raise ValueError("max_attachments must be non-negative")
        return value

    @field_validator("max_bytes")
    @classmethod
    def _validate_max_bytes(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("max_bytes must be positive")
        return value


class TemplateCall(llm.Toolbox):
    """Call another llm template with carefully scoped context."""

    name = "TemplateCall"

    def __init__(
        self,
        config: Optional[dict] = None,
        *,
        allow_templates: Optional[List[str]] = None,
        allowed_suffixes: Optional[List[str]] = None,
        max_attachments: Optional[int] = None,
        max_bytes: Optional[int] = None,
        ignore_functions: Optional[bool] = None,
        lock_template: Optional[str] = None,
        default_model: Optional[str] = None,
    ):
        if config is not None and not isinstance(config, dict):
            raise TypeError("TemplateCall config must be a dict")
        options = dict(config or {})
        if allow_templates is not None:
            options["allow_templates"] = allow_templates
        if allowed_suffixes is not None:
            options["allowed_suffixes"] = allowed_suffixes
        if max_attachments is not None:
            options["max_attachments"] = max_attachments
        if max_bytes is not None:
            options["max_bytes"] = max_bytes
        if ignore_functions is not None:
            options["ignore_functions"] = ignore_functions
        if lock_template is not None:
            options["lock_template"] = lock_template
        if default_model is not None:
            options["default_model"] = default_model

        self.config = TemplateCallConfig(**options)

    # tool method ------------------------------------------------------
    def run(
        self,
        template: str,
        input: str = "",
        attachments: Optional[List[str]] = None,
        fragments: Optional[List[str]] = None,
        params: Optional[dict] = None,
        expect_json: bool = False,
    ) -> str:
        template_name = self.config.lock_template or template
        if not template_name:
            raise ValueError("Template path is required")
        if not self._template_allowed(template_name):
            raise ValueError(f"Template '{template_name}' is not allowed")

        tmpl = self._load_template(template_name)

        param_values = params or {}
        if not isinstance(param_values, dict):
            raise TypeError("params must be a dictionary")
        try:
            prompt_text, system_text = tmpl.evaluate(input or "", params=param_values)
        except Template.MissingVariables as exc:
            raise ValueError(str(exc)) from exc
        fragment_list = list(tmpl.fragments or [])
        if fragments:
            if not isinstance(fragments, list):
                raise TypeError("fragments must be a list of strings")
            fragment_list.extend(str(f) for f in fragments)

        system_fragment_list = list(tmpl.system_fragments or [])

        attachment_inputs = attachments or []
        if not isinstance(attachment_inputs, list):
            raise TypeError("attachments must be a list of paths")
        attachment_objs = self._resolve_attachments(attachment_inputs)

        tool_instances = self._instantiate_tools(tmpl)

        model_name = (
            tmpl.model or self.config.default_model or llm.get_default_model()
        )
        model = llm.get_model(model_name)

        response = model.prompt(
            prompt_text or "",
            system=system_text,
            attachments=attachment_objs or None,
            fragments=fragment_list or None,
            system_fragments=system_fragment_list or None,
            schema=tmpl.schema_object,
            tools=tool_instances or None,
            stream=False,
            **(tmpl.options or {}),
        )
        text = response.text()
        if expect_json:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError("Template did not return valid JSON") from exc
            return json.dumps(payload, sort_keys=True, indent=2)
        return text

    # helpers ----------------------------------------------------------
    def _template_allowed(self, name: str) -> bool:
        if not self.config.allow_templates:
            return True
        candidates = [name]
        if not name.startswith("pkg:"):
            try:
                candidates.append(str(Path(name).resolve()))
            except FileNotFoundError:
                pass
        return any(
            fnmatch.fnmatch(candidate, pattern)
            for candidate in candidates
            for pattern in self.config.allow_templates
        )

    def _load_template(self, name: str) -> Template:
        cli = _llm_cli_module()
        LoadTemplateError = cli.LoadTemplateError
        parse_template = cli._parse_yaml_template
        if name.startswith("pkg:"):
            relative = name.split(":", 1)[1]
            package_root = resources.files("llm_do.templates")
            resource = package_root.joinpath(relative)
            if not resource.is_file():
                raise LoadTemplateError(f"Template not found in package: {relative}")
            content = resource.read_text(encoding="utf-8")
            template = parse_template(name, content)
            template._functions_is_trusted = True
            return template
        path = Path(name)
        if not path.exists():
            raise LoadTemplateError(f"Template not found: {name}")
        content = path.read_text(encoding="utf-8")
        template = parse_template(str(path), content)
        template._functions_is_trusted = True
        return template

    def _resolve_attachments(self, attachment_paths: List[str]) -> List[llm.Attachment]:
        if len(attachment_paths) > self.config.max_attachments:
            raise ValueError("Too many attachments")
        attachments: List[llm.Attachment] = []
        total = 0
        for raw in attachment_paths:
            path = Path(raw).expanduser().resolve()
            if not path.is_file():
                raise FileNotFoundError(raw)
            suffix = path.suffix.lower()
            if self.config.allowed_suffixes and suffix not in self.config.allowed_suffixes:
                raise ValueError(f"Attachment suffix '{suffix}' not allowed")
            size = path.stat().st_size
            total += size
            if total > self.config.max_bytes:
                raise ValueError("Attachments exceed max_bytes limit")
            attachments.append(llm.Attachment(path=str(path)))
        return attachments

    def _instantiate_tools(self, template: Template):
        cli = _llm_cli_module()
        if not template.tools and (
            self.config.ignore_functions or not template.functions
        ):
            return None
        tools = []
        registered = llm.get_tools()
        class_map = {
            name: value
            for name, value in registered.items()
            if inspect.isclass(value)
        }
        for spec in template.tools or []:
            spec = spec.strip()
            if not spec:
                continue
            if spec[0].isupper():
                tools.append(cli.instantiate_from_spec(class_map, spec))
            else:
                if spec not in registered:
                    raise ValueError(f"Unknown tool '{spec}' in template")
                tools.append(registered[spec])
        if not self.config.ignore_functions and template.functions:
            if not template._functions_is_trusted:
                raise ValueError("Template functions are not trusted")
            tools.extend(cli._tools_from_code(textwrap.dedent(template.functions)))
        return tools


__all__: Iterable[str] = ["TemplateCall"]
