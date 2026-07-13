from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTED_CONFIG = "examples/config.scripted.yaml"
EVAL_CONFIG = "examples/config.eval-scripted.yaml"
EVAL_CORPUS = "examples/eval-corpus.yaml"


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


def test_scripted_eval_example_reports_cost_premium() -> None:
    result = cli(
        "eval",
        "--config",
        EVAL_CONFIG,
        "--corpus",
        EVAL_CORPUS,
        "--json",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["case_count"] == 2
    assert report["arms"]["orchestrated"]["passes"] == 2
    assert report["arms"]["single_call"]["passes"] == 2
    # Orchestration runs three model calls per case; the single call runs one.
    assert report["arms"]["orchestrated"]["calls"] == 6
    assert report["arms"]["single_call"]["calls"] == 2
    assert (
        report["arms"]["orchestrated"]["total_tokens"]
        > report["arms"]["single_call"]["total_tokens"]
    )
    # The single-call control's compute ratio vs orchestration is reported.
    assert report["arms"]["single_call"]["compute_ratio_vs_treatment"] < 1.0


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
