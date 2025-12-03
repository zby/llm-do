# Single-File Workers

## Motivation

Workers as single files would match the intuition of an executable:
- `chmod +x my_worker.worker && ./my_worker.worker "do something"`
- Easy to share, copy, version
- Self-contained unit of behavior
- Similar to shell scripts or Python scripts

Current directory-based model feels heavyweight for simple workers.

## Current Model (Directory-Based)

```
project/
  workers/
    orchestrator/
      worker.worker     # YAML frontmatter + instructions
      tools.py          # Custom Python tools
      templates/
        report.md
    analyzer/
      worker.worker
```

**Pros:**
- Clear place for resources (tools, templates)
- Natural grouping of related files

**Cons:**
- Heavyweight for simple workers
- Doesn't feel like "running a program"
- Harder to share a single worker

## Single-File Model

```
project/
  workers/
    orchestrator.worker
    analyzer.worker
    helper.worker
```

Or even flatter:
```
~/bin/
  code-reviewer.worker
  git-helper.worker
```

## Challenges

### 1. Custom Python Tools

**Option A: Embed in file**
```yaml
---
name: my_worker
---
You are a helper...

```python tools
def analyze(text: str) -> dict:
    """Analyze the text."""
    return {"length": len(text)}
```
```

Pros: Truly single-file
Cons: Mixing languages, hard to test tools separately, no IDE support for embedded Python

**Option B: Reference external module**
```yaml
---
name: my_worker
toolsets:
  custom:
    module: myproject.tools.analyzer
---
```

Pros: Clean separation, testable
Cons: Not truly single-file, need to manage Python path

**Option C: Adjacent file convention**
```
my_worker.worker
my_worker.tools.py  # Auto-discovered if exists
```

Pros: Related files stay together, optional
Cons: Still multiple files

**Option D: No custom tools in single-file workers**

Single-file workers only use built-in toolsets. If you need custom tools, use directory model.

### 2. Worker Search Path (Delegation)

When `orchestrator.worker` calls `worker_call("analyzer")`, where to find `analyzer`?

**Option A: Same directory**
```yaml
# orchestrator.worker delegates to analyzer.worker in same dir
toolsets:
  delegation:
    allow_workers: [analyzer]  # looks for analyzer.worker nearby
```

**Option B: Explicit paths**
```yaml
toolsets:
  delegation:
    allow_workers:
      - ./analyzer.worker
      - /shared/workers/helper.worker
```

**Option C: Registry config**
```yaml
# llm-do.yaml or similar
worker_paths:
  - ./workers
  - ~/.llm-do/workers
  - /usr/share/llm-do/workers
```

**Option D: Environment variable**
```bash
export LLM_DO_PATH="./workers:~/.llm-do/workers"
llm-do orchestrator.worker "do something"
```

Similar to `PATH` for executables.

### 3. Templates and Resources

**Option A: Embed small templates**
```yaml
---
name: reporter
templates:
  report: |
    # Report for {{title}}
    Generated on {{date}}
---
```

**Option B: Reference external files**
```yaml
---
templates:
  report: ./templates/report.md
---
```

**Option C: Adjacent directory convention**
```
reporter.worker
reporter.resources/
  templates/
    report.md
```

### 4. Shebang Support

For true executable feel:
```
#!/usr/bin/env llm-do
---
name: git-helper
toolsets:
  shell:
    rules:
      - pattern: "git *"
        approval_required: false
---
You help with git operations...
```

Then:
```bash
chmod +x git-helper.worker
./git-helper.worker "what changed since yesterday?"
```

## Proposed Hybrid Approach

Support both models:

1. **Single-file workers** (`.worker` extension):
   - Self-contained instructions + config
   - Built-in toolsets only (shell, delegation, sandbox)
   - Templates embedded or referenced
   - Good for: simple helpers, scripts, shareable workers

2. **Directory workers** (directory with `worker.worker`):
   - Full power: custom Python tools, local resources
   - Good for: complex workers, workers with custom logic

3. **Search path** (like `PATH`):
   - `LLM_DO_PATH` environment variable
   - Or config in `~/.llm-do/config.yaml`
   - Directories searched for `.worker` files and worker directories

4. **Shebang support**:
   - Workers can be directly executable
   - `#!/usr/bin/env llm-do` at top (before YAML frontmatter)

## Migration

Current directory-based workers continue to work. Single-file is additive.

## Open Questions

1. **File extension**: `.worker` vs `.llm` vs `.agent`?
2. **Custom tools**: Which option for embedding/referencing?
3. **Priority**: If both `foo.worker` and `foo/worker.worker` exist, which wins?
4. **Imports**: Can single-file workers import/extend other workers?
5. **Security**: How to handle workers from untrusted sources?
