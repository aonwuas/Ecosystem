from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTED_CONFIG = "examples/config.scripted.yaml"


def cli(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    env["PYTHONPATH"] = (
        src_path
        if not env.get("PYTHONPATH")
        else os.pathsep.join([src_path, env["PYTHONPATH"]])
    )
    return subprocess.run(
        [sys.executable, "-m", "prompt_orchestrator", *args],
        cwd=ROOT,
        env=env,
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )


def test_scripted_example_config_validates() -> None:
    result = cli("config", "validate", "--config", SCRIPTED_CONFIG)

    assert result.returncode == 0
    assert "Configuration valid." in result.stdout
    assert "scripted_general" in result.stdout


def test_scripted_example_understand_plan_and_run() -> None:
    prompt = "Help me choose between SQLite and PostgreSQL"

    understand = cli("understand", "--config", SCRIPTED_CONFIG, "--json", prompt)
    plan = cli("plan", "--config", SCRIPTED_CONFIG, "--json", prompt)
    run = cli("run", "--config", SCRIPTED_CONFIG, "--json", prompt)

    assert understand.returncode == 0
    assert json.loads(understand.stdout)["plan"]["strategy"] == "comparison"
    assert plan.returncode == 0
    assert json.loads(plan.stdout)["status"] == "planned"
    assert run.returncode == 0
    payload = json.loads(run.stdout)
    assert payload["status"] == "completed"
    assert "SQLite" in payload["text"]
    assert "PostgreSQL" in payload["text"]


def test_scripted_example_stdin_and_trace() -> None:
    request_text = (ROOT / "examples" / "request.txt").read_text(encoding="utf-8")

    result = cli(
        "run",
        "--config",
        SCRIPTED_CONFIG,
        "--stdin",
        "--json",
        "--trace",
        stdin=request_text,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["trace"]["events"]
    assert request_text.strip() not in json.dumps(payload["trace"])
