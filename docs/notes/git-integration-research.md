# Git Integration Research

## Context

Investigating git integration patterns from other Python CLI AI assistants (particularly Aider) and the TypeScript port (golem-forge) to inform potential git toolset for llm-do.

## Aider's Git Architecture

Aider (Python, 80% of codebase) has deep git integration via GitPython:

### Key Features
- **Auto-commit**: Commits after each successful edit
- **AI commit messages**: Uses a "weak model" to generate messages from diffs
- **Dirty file handling**: Commits pre-existing changes before editing
- **Attribution**: Appends "(aider)" to author/committer metadata
- **Co-authored-by trailers**: Optional credit to AI model

### Implementation Pattern
```python
import git  # GitPython

class GitRepo:
    def __init__(self, io, fnames, git_dname, ...):
        # Finds repo, validates all files belong to single repo

    def commit(self, fnames, context, message=None, aider_edits=True):
        # Generates commit message if not provided
        # Sets GIT_AUTHOR_NAME, GIT_COMMITTER_NAME env vars
        # Handles attribution based on aider_edits flag

    def get_diffs(self, fnames=None):
        # Unified diffs for dirty files

    def get_commit_message(self, diffs, context):
        # Sends diffs to weak model for message generation
```

### Configurable Behaviors
- `--no-auto-commits` - disable auto-commit
- `--no-dirty-commits` - don't commit dirty files first
- `--no-git` - disable git entirely
- `--commit-prompt` - customize message generation prompt
- `--git-commit-verify` - enable/disable pre-commit hooks

Reference: https://aider.chat/docs/git.html

## golem-forge Git Integration

The TypeScript port at `../golem-forge` has a sophisticated git toolset:

### Architecture
```
packages/core/src/tools/git/
├── types.ts          # Type definitions, Zod schemas
├── backend.ts        # Abstract GitBackend interface
├── tools.ts          # 9 git tool implementations
├── merge.ts          # 3-way merge algorithm
└── isomorphic-backend.ts  # Browser-compatible backend

packages/cli/src/tools/git/
├── cli-backend.ts    # Native git CLI + isomorphic-git
├── auth.ts           # GitHub token handling
└── index.ts          # Tool registration
```

### Tools Provided
1. `git_status` - Show staged commits and unstaged files
2. `git_stage` - Stage files for commit (needs approval)
3. `git_diff` - Show unified diffs
4. `git_push` - Push staged commit (manual-only, LLM cannot invoke)
5. `git_discard` - Discard a staged commit
6. `git_pull` - Pull files with 3-way merge on conflict
7. `git_merge` - Standalone merge utility
8. `git_branches` - List branches
9. `git_check_conflicts` - Check for unresolved markers

### Key Design: Staged Commits Model
```
Working Files → git_stage (approval) → Staged Commit → git_push (manual) → Git Repo
```

This provides strong guardrails:
- Read-only operations: pre-approved
- Staging: requires approval
- Push: manual-only (user must explicitly invoke)

### Git Target Types
- `github`: "owner/repo" format via Octokit API
- `local`: Local filesystem repos via native git CLI

### Configuration Example
```yaml
git:
  default_target:
    type: local
    path: "."
  credentials:
    mode: "inherit"  # uses system git config
```

## Current llm-do State

- No dedicated git toolset
- Git available only via shell tool with manual rules:
  ```yaml
  toolsets:
    shell:
      rules:
      - pattern: git log
      - pattern: git diff
  ```

## Proposed Approaches for llm-do

### Option 1: Simple Git Toolset (Low complexity)

Follow shell toolset pattern:
```
llm_do/git/
├── toolset.py      # GitToolset(AbstractToolset)
├── execution.py    # GitPython operations
└── types.py        # GitResult, GitRule models
```

Tools: `git_status`, `git_diff`, `git_log`, `git_add`, `git_commit`

Configuration:
```yaml
toolsets:
  git:
    rules:
    - pattern: status
    - pattern: diff
    - pattern: add
      approval_required: true
    - pattern: commit
      approval_required: true
```

### Option 2: Staged Commits (Medium complexity)

Port golem-forge's staged commit model:
- Track file modifications in working directory
- Stage changes before committing
- Require explicit approval for push

### Option 3: Auto-commit (Higher complexity)

Aider-style integration:
- Hook into filesystem toolset to track modifications
- Auto-commit on worker completion
- AI-generated commit messages via weak model
- Attribution to worker name

## Recommendations

1. **Start with Option 1** - basic git toolset following shell pattern
2. **Reuse golem-forge patterns** where applicable (staged commits model)
3. **Consider GitPython** for Python implementation (Aider's choice)
4. **Approval gates** essential for write operations (add, commit, push)

## Open Questions
- Should llm-do adopt staged commits now or start with a minimal git toolset?
- Do we prefer GitPython or invoking the git CLI for early iterations?
- How should approvals and manual-only operations map to git push and pull?

## References

- Aider git docs: https://aider.chat/docs/git.html
- Aider repo.py: https://github.com/Aider-AI/aider/blob/main/aider/repo.py
- golem-forge git toolset: ../golem-forge/packages/core/src/tools/git/
- golem-forge git docs: ../golem-forge/docs/git-toolset.md
