"""
Core execution logic for llm-do

Executes spec-driven workflows by providing tools to LLM and letting it
interpret natural language commands according to a specification.
"""

import llm
from llm.models import CancelToolCall
from datetime import datetime
from typing import Optional
import click

from .context import WorkflowContext


class ToolApprovalCallback:
    """
    Stateful callback for approving tool executions.

    Allows user to approve each tool call individually, or approve all
    tool calls for the duration of the session.
    """

    def __init__(self):
        self.approve_all = False

    def __call__(self, tool, tool_call):
        """Called before each tool execution."""
        # If user previously approved all, skip prompting
        if self.approve_all:
            return

        # Display the tool call
        click.echo(
            click.style(
                f"\nTool call: {tool_call.name}({tool_call.arguments})",
                fg="yellow",
                bold=True,
            ),
            err=True,
        )

        # Prompt for approval
        while True:
            response = click.prompt(
                "Approve? [y]es, [n]o, [a]lways, [q]uit",
                type=str,
                default="y",
                err=True,
            ).lower().strip()

            if response in ("y", "yes", ""):
                return  # Approve this tool call
            elif response in ("n", "no"):
                raise CancelToolCall("User declined tool call")
            elif response in ("a", "always"):
                self.approve_all = True
                click.echo(
                    click.style("✓ All tool calls approved for this session", fg="green"),
                    err=True,
                )
                return
            elif response in ("q", "quit"):
                raise CancelToolCall("User quit")
            else:
                click.echo("Invalid response. Please enter y, n, a, or q.", err=True)


def execute_spec(
    task: str,
    *,
    context: WorkflowContext,
    model_name: Optional[str] = None,
    verbose: bool = True,
    tools_approve: bool = False,
):
    """
    Execute a task according to a specification using LLM + tools.

    Args:
        task: Natural language task description
        context: WorkflowContext containing config, spec, toolbox
        model_name: LLM model to use (defaults to llm's configured default)
        verbose: Print execution details
        tools_approve: Manually approve every tool execution

    Returns:
        Response text from LLM

    Raises:
        FileNotFoundError: If spec file doesn't exist
        Exception: If model or execution fails
    """

    spec_path = context.spec_path
    prompt_text, system_text = context.build_prompt(task)

    resolved_model_name = context.resolve_model_name(model_name)

    if verbose:
        print(f"Task: {task}")
        print(f"Spec: {spec_path}")
        if context.config.prompt.template:
            print(f"Template: {context.config.prompt.template}")
        print(f"Model: {resolved_model_name}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("=" * 60)
        print()

    try:
        model = llm.get_model(resolved_model_name)
    except Exception as e:
        raise Exception(f"Error loading model {resolved_model_name}: {e}")

    context.ensure_model_allowed(model, resolved_model_name)

    if verbose:
        print(f"Executing with {resolved_model_name}...")
        print()

    # Execute with tool chain
    try:
        # Set up approval callback if requested
        before_call = None
        if tools_approve:
            before_call = ToolApprovalCallback()

        chain_response = model.chain(
            prompt_text,
            system=system_text,
            tools=[context.toolbox],  # Toolbox must be in a list
            before_call=before_call,
        )

        # Collect response text
        response_text = []
        for chunk in chain_response:
            if verbose:
                print(chunk, end="", flush=True)
            response_text.append(chunk)

        if verbose:
            print()  # Final newline
            print()
            print("=" * 60)
            print()
            print("Complete!")

        return "".join(response_text)

    except KeyboardInterrupt:
        if verbose:
            print("\n\nInterrupted by user")
        raise
    except Exception as e:
        if verbose:
            print(f"\n\nError during execution: {e}")
        raise
