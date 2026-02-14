"""Live integration test for injected non-streaming provider wrappers."""

import os
import subprocess
import sys
from pathlib import Path

from .conftest import skip_no_llm


@skip_no_llm
def test_cli_init_python_injected_non_streaming_provider_runs(greeter_example, default_model):
    """Injected non-streaming wrappers should still run in headless -v mode."""
    repo_root = Path(__file__).resolve().parents[2]
    python_exe = repo_root / ".venv" / "bin" / "python"
    if not python_exe.exists():
        python_exe = Path(sys.executable)

    init_module = Path(__file__).with_name("nostream_provider.py").resolve()

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
