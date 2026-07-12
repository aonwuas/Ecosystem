from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.live
def test_live_openai_compatible_run() -> None:
    config_path = os.environ.get("PROMPT_ORCHESTRATOR_LIVE_CONFIG")
    if not config_path:
        pytest.skip("Set PROMPT_ORCHESTRATOR_LIVE_CONFIG to run live smoke test.")

    prompt = os.environ.get(
        "PROMPT_ORCHESTRATOR_LIVE_PROMPT",
        "Give one short practical tip for planning a small software project.",
    )
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = (
        src_path
        if not env.get("PYTHONPATH")
        else os.pathsep.join([src_path, env["PYTHONPATH"]])
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "prompt_orchestrator",
            "run",
            "--config",
            config_path,
            "--json",
            prompt,
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=240,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] in {"completed", "completed_with_warnings"}
    assert payload["text"].strip()
