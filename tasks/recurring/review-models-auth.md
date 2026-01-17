# Review: Models and Auth

Periodic review of model selection and authentication modules.

## Scope

- `llm_do/models.py` - Model selection and compatibility
- `llm_do/oauth/` - OAuth implementation
- `llm_do/cli/oauth.py` - OAuth CLI commands

## Checklist

- [ ] Model selection logic is correct
- [ ] OAuth flow is secure and functional
- [ ] Error messages are helpful
- [ ] No sensitive data exposure

## Output

Record findings in `docs/notes/reviews/review-models-auth.md`.

## Last Run

2026-01 (reviewed model selection + OAuth; main gaps: model precedence docs mismatch, OAuth overrides not integrated)
