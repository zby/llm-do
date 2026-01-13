"""RLM-style REPL tooling and entry point."""
from __future__ import annotations

import io
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic_ai.toolsets import FunctionToolset
from RestrictedPython import (
    compile_restricted_exec,
    limited_builtins,
    safe_globals,
    utility_builtins,
)
from RestrictedPython.Guards import guarded_iter_unpack_sequence, safer_getattr
from RestrictedPython.PrintCollector import PrintCollector

from llm_do.runtime import ToolsetSpec, WorkerInput, WorkerRuntime, entry
from llm_do.toolsets.approval import set_toolset_approval_config

_STATE: dict[str, Any] = {
    "context": "",
    "query": "",
    "env": {},
}


class REPLError(Exception):
    """Error during REPL execution."""


class REPLExecutor:
    """RestrictedPython REPL executor with a safe stdlib whitelist."""

    def __init__(self, max_output_chars: int = 2000) -> None:
        self.max_output_chars = max_output_chars

    def execute(self, code: str, env: dict[str, Any]) -> str:
        code = self._extract_code(code)
        if not code.strip():
            return "No code to execute"

        restricted_globals = self._build_globals()

        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()

        try:
            byte_code = compile_restricted_exec(code)
            if byte_code.errors:
                raise REPLError(f"Compilation error: {', '.join(byte_code.errors)}")

            exec(byte_code.code, restricted_globals, env)

            output = captured_output.getvalue()
            output = self._append_print_collector(env, output)
            output = self._append_last_expression(code, restricted_globals, env, output)

            if not output:
                return "Code executed successfully (no output)"

            if len(output) > self.max_output_chars:
                truncated = output[: self.max_output_chars]
                return (
                    f"{truncated}\n\n"
                    f"[Output truncated: {len(output)} chars total, "
                    f"showing first {self.max_output_chars}]"
                )

            return output.strip()
        except Exception as exc:
            raise REPLError(f"Execution error: {exc}") from exc
        finally:
            sys.stdout = old_stdout

    def _append_print_collector(self, env: dict[str, Any], output: str) -> str:
        print_collector = env.get("_print")
        if print_collector is not None and hasattr(print_collector, "txt"):
            output += "".join(print_collector.txt)
        return output

    def _append_last_expression(
        self,
        code: str,
        restricted_globals: dict[str, Any],
        env: dict[str, Any],
        output: str,
    ) -> str:
        lines = code.strip().split("\n")
        if not lines:
            return output

        last_line = lines[-1].strip()
        if not last_line:
            return output

        if any(kw in last_line for kw in ["=", "import", "def", "class", "if", "for", "while", "with"]):
            return output

        try:
            result = eval(last_line, restricted_globals, env)
        except Exception:
            return output

        if result is None:
            return output

        return f"{output}{result}\n"

    def _extract_code(self, text: str) -> str:
        if "```python" in text:
            start = text.find("```python") + len("```python")
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()

        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                return text[start:end].strip()

        return text

    def _build_globals(self) -> dict[str, Any]:
        restricted_globals = safe_globals.copy()
        restricted_globals.update(limited_builtins)
        restricted_globals.update(utility_builtins)

        restricted_globals.update({
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
            "_getattr_": safer_getattr,
            "_getitem_": lambda obj, index: obj[index],
            "_getiter_": iter,
            "_print_": PrintCollector,
        })

        restricted_globals.update({
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "frozenset": frozenset,
            "bytes": bytes,
            "bytearray": bytearray,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "reversed": reversed,
            "iter": iter,
            "next": next,
            "sorted": sorted,
            "sum": sum,
            "min": min,
            "max": max,
            "any": any,
            "all": all,
            "abs": abs,
            "round": round,
            "pow": pow,
            "divmod": divmod,
            "chr": chr,
            "ord": ord,
            "hex": hex,
            "oct": oct,
            "bin": bin,
            "repr": repr,
            "ascii": ascii,
            "format": format,
            "isinstance": isinstance,
            "issubclass": issubclass,
            "callable": callable,
            "type": type,
            "hasattr": hasattr,
            "True": True,
            "False": False,
            "None": None,
        })

        import json
        import math
        import re

        restricted_globals.update({
            "re": re,
            "json": json,
            "math": math,
            "datetime": datetime,
            "timedelta": timedelta,
            "Counter": Counter,
            "defaultdict": defaultdict,
        })

        return restricted_globals


_REPL = REPLExecutor()


def set_context(text: str, query: str) -> None:
    """Load the external context into the persistent REPL environment."""
    _STATE["context"] = text
    _STATE["query"] = query
    env = _STATE["env"]
    env["context"] = text
    env["query"] = query


def build_rlm_tools(_ctx):
    tools = FunctionToolset()

    @tools.tool
    def repl(code: str) -> str:
        """Execute Python in a restricted REPL with `context` preloaded."""
        env = _STATE["env"]
        env["context"] = _STATE["context"]
        env["query"] = _STATE["query"]

        try:
            return _REPL.execute(code, env)
        except REPLError as exc:
            return f"Error: {exc}"
        except Exception as exc:
            return f"Unexpected error: {exc}"

    set_toolset_approval_config(
        tools,
        {"repl": {"pre_approved": True}},
    )
    return tools


rlm_tools = ToolsetSpec(factory=build_rlm_tools)

PROJECT_ROOT = Path(__file__).parent.resolve()
CONTEXT_PATH = PROJECT_ROOT / "context.txt"


@entry(name="main", schema_in=WorkerInput, toolsets=["rlm"])
async def main(args: WorkerInput, runtime: WorkerRuntime) -> str:
    """Load context and run the RLM worker with the user query."""
    query = args.input.strip() or "Summarize the context."
    set_context(CONTEXT_PATH.read_text(encoding="utf-8"), query)
    return await runtime.call("rlm", WorkerInput(input=query))
