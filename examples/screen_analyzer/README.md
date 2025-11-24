# Screen Analyzer Example

This example demonstrates how to create workers with custom tools for computer interaction and screen analysis, following patterns for integrating with **Anthropic Computer Use (ACI.dev)**.

## What This Shows

- **Custom tools for computer interaction**: Screenshot analysis, text extraction, element detection
- **Integration pattern for Anthropic Computer Use**: Placeholder implementations show the structure
- **Attachment-based workflows**: Workers receive images as attachments for analysis
- **Security considerations**: Tool approvals and sandboxing for computer interaction

## Structure

```
screen_analyzer/
├── workers/
│   └── screen_analyzer/
│       ├── worker.yaml       # Worker configuration
│       └── tools.py          # Custom computer interaction tools
└── screenshots/              # Screenshot attachments directory
```

## Custom Tools

The worker has three custom tools in `tools.py`:

1. `get_screen_info(screen_name)` - Get screen/display information
2. `extract_text_regions(image_ref, regions)` - OCR and text extraction from images
3. `get_element_positions(image_ref, element_type, query)` - Find UI elements in screenshots

These are **placeholder implementations** that demonstrate the pattern. For production use, integrate with Anthropic's Computer Use tools.

## Usage (Placeholder Mode)

```bash
# Analyze a screenshot (simulated)
llm-do screen_analyzer "What screen resolution is available?" --approve-all

# With actual screenshot (when available)
# llm-do screen_analyzer "Describe this interface" \
#   --attach screenshots/app.png --approve-all
```

## Integrating with Anthropic Computer Use

To use **real** Anthropic Computer Use capabilities:

### 1. Prerequisites

- Anthropic API key with Computer Use access
- Claude 3.5 Sonnet (20241022 or later)
- Appropriate security setup (sandboxing, containers)

### 2. Update tools.py

Replace placeholder implementations with real Anthropic Computer Use API calls:

```python
from anthropic import Anthropic

client = Anthropic(api_key="your-api-key")

def get_screen_info(screen_name: str = "primary") -> Dict[str, any]:
    """Real computer use implementation."""
    # Use Anthropic's computer_use tools via the API
    # See: https://docs.anthropic.com/en/docs/agents/computer-use
    ...
```

### 3. Security Considerations

When using real computer use:

- **Sandboxing**: Run in isolated containers/VMs
- **Approval workflows**: Require human approval for sensitive actions
- **Access controls**: Limit what the assistant can interact with
- **Audit logging**: Track all computer interactions
- **Rate limiting**: Prevent abuse

Update `tool_rules` in `worker.yaml`:

```yaml
tool_rules:
  get_screen_info:
    allowed: true
    approval_required: true  # Require approval in production
    description: Screen capture requires explicit approval
```

## Anthropic Computer Use Resources

- [Computer Use Documentation](https://docs.anthropic.com/en/docs/agents/computer-use)
- [Computer Use Best Practices](https://docs.anthropic.com/en/docs/agents/computer-use#best-practices)
- [Security Guidelines](https://docs.anthropic.com/en/docs/agents/computer-use#security)

## Example Workflow

1. **Screenshot capture**: Attach screenshot images to worker input
2. **Analysis**: Worker uses custom tools to analyze the image
3. **Interaction planning**: Worker suggests actions based on screen content
4. **Execution**: (In production) Execute approved actions via Computer Use API

## Extending This Example

You can add more computer interaction tools:

- `click_element(x, y)` - Simulate mouse clicks
- `type_text(text)` - Simulate keyboard input
- `scroll_page(direction, amount)` - Scroll content
- `run_command(cmd)` - Execute bash commands (with approval)

Each tool should:
- Have clear docstrings for the LLM
- Include type hints for validation
- Follow security best practices
- Be subject to approval rules
