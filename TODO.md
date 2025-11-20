# TODO

## Upstream Discussion

- [ ] **Coordinate with llm maintainers on TemplateCall hooks**

  `TemplateCall` currently sneaks around the public API in two places:
  1. Nested calls: when workers call other templates via `model.prompt()` we bypass the CLI, so CLI flags (`--tools`, `--tools-debug`, etc.) and future per-run options never reach sub-templates. We paper over this gap with `LLM_DO_DEBUG=1`, but it's brittle and doesn't scale to other switches.
  2. Template parsing: we import the CLI module and call its private `_parse_yaml_template()` helper so we can reuse fragment/attachment syntax. That function is not part of a stable API, so any change in the upstream CLI could break us.

  We should ask for guidance on an official surface area that covers both needs. Possibilities include a context object that carries CLI/UX preferences into nested prompts plus a supported template loader/parsing helper (or a way to register our own Template implementation). Until then we keep relying on private internals.

  Current workaround for debug visibility: `LLM_DO_DEBUG=1 llm -t template.yaml "task"`
