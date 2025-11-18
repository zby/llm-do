"""
LLM plugin registration for llm-do

Registers the 'llm do' command with the llm CLI tool.
"""

import click
import llm
from pathlib import Path
from .executor import execute_spec
from .toolbox import BaseToolbox
from .context import WorkflowContext


@llm.hookimpl
def register_commands(cli):
    """Register the 'do' command with llm CLI"""

    @cli.command()
    @click.argument("task")
    @click.option(
        "--spec",
        "-s",
        type=click.Path(exists=True),
        help="Path to specification file (otherwise resolved via llm-do config)",
    )
    @click.option(
        "--working-dir",
        "-d",
        type=click.Path(exists=True, file_okay=False),
        help="Working directory for file operations (default: current directory)",
    )
    @click.option(
        "--model",
        "-m",
        default=None,
        help="Model to use (default: llm\'s configured default)",
    )
    @click.option(
        "--quiet",
        "-q",
        is_flag=True,
        help="Suppress verbose output",
    )
    @click.option(
        "--toolbox",
        "-t",
        help="Python path to custom toolbox class (e.g., mymodule.MyToolbox)",
    )
    @click.option(
        "tools_approve",
        "--ta",
        "--tools-approve",
        is_flag=True,
        help="Manually approve every tool execution",
    )
    def do(task, spec, working_dir, model, quiet, toolbox, tools_approve):
        """
        Execute a task according to a specification.

        The task should be a natural language description of what you want to do.
        The spec file defines the workflow and how to interpret tasks.

        Examples:

            llm do "process all PDFs in pipeline/"

            llm do "generate questions for CompanyX" --spec ./SPEC.md

            llm do "re-evaluate all" -d /path/to/project
        """
        # Set working directory
        if not working_dir:
            working_dir = Path.cwd()
        else:
            working_dir = Path(working_dir)

        # Get toolbox
        if toolbox:
            # Import custom toolbox
            try:
                module_path, class_name = toolbox.rsplit(".", 1)
                import importlib
                module = importlib.import_module(module_path)
                toolbox_class = getattr(module, class_name)
                toolbox_instance = toolbox_class(working_dir=working_dir)
            except Exception as e:
                raise click.ClickException(f"Error loading toolbox {toolbox}: {e}")
        else:
            # Use base toolbox
            toolbox_instance = BaseToolbox(working_dir=working_dir)

        try:
            context = WorkflowContext(
                working_dir=working_dir,
                spec_path=spec,
                toolbox=toolbox_instance,
            )
        except click.ClickException:
            raise
        except Exception as e:
            raise click.ClickException(str(e))

        # Execute
        try:
            execute_spec(
                task=task,
                context=context,
                model_name=model,
                verbose=not quiet,
                tools_approve=tools_approve,
            )
        except KeyboardInterrupt:
            click.echo("\nInterrupted", err=True)
            raise SystemExit(1)
        except Exception as e:
            raise click.ClickException(str(e))
