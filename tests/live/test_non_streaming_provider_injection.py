"""Live integration test for injected non-streaming provider wrappers."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

from .conftest import skip_no_llm


@skip_no_llm
def test_cli_init_python_injected_non_streaming_provider_runs(greeter_example, default_model):
    """Injected non-streaming wrappers should still run in headless -v mode."""
    repo_root = Path(__file__).resolve().parents[2]
    python_exe = repo_root / ".venv" / "bin" / "python"
    if not python_exe.exists():
        python_exe = Path(sys.executable)

    init_module = greeter_example / "nostream_provider.py"
    init_module.write_text(
        textwrap.dedent(
            """
            from pydantic_ai.models import Model, infer_model

            from llm_do import register_model_factory


            class NonStreamingModel(Model):
                def __init__(self, inner: Model) -> None:
                    super().__init__()
                    self._inner = inner

                @property
                def model_name(self) -> str:
                    return self._inner.model_name

                @property
                def system(self) -> str:
                    return self._inner.system

                async def request(self, messages, model_settings, model_request_parameters):
                    return await self._inner.request(messages, model_settings, model_request_parameters)


            def build_nostream(model_name: str) -> Model:
                return NonStreamingModel(infer_model(model_name))


            register_model_factory("nostream_live", build_nostream, replace=True)
            """
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["LLM_DO_MODEL"] = f"nostream_live:{default_model}"
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{repo_root}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(repo_root)
    )

    proc = subprocess.run(
        [
            str(python_exe),
            "-m",
            "llm_do.cli.main",
            str(greeter_example / "project.json"),
            "Say hi in three words.",
            "--headless",
            "-v",
            "--init-python",
            str(init_module),
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip()
