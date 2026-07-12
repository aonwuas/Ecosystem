from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def plan_payload(
    *,
    action: str = "proceed",
    question: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "understanding": {
            "user_goal": "Choose the more appropriate database.",
            "intent": "decision support",
            "task_type": "comparison",
            "complexity": "moderate",
            "ambiguity": "medium",
            "risk_level": "low",
            "risk_categories": [],
            "missing_information": ["expected concurrency"],
            "assumptions": ["The application is early-stage."],
            "uncertainties": ["Expected concurrency is unknown."],
            "concise_rationale": "The user is comparing database options.",
        },
        "clarification": {
            "action": action,
            "question": question,
            "reason": (
                "A conditional answer is useful."
                if action == "proceed"
                else "A required detail is missing."
            ),
        },
        "strategy": "comparison",
        "worker_role": "worker",
        "output_contract": {
            "mode": "markdown",
            "structure": "comparison with recommendation",
            "tone": "practical",
            "length": "medium",
            "audience": "developer",
        },
        "must_include": ["tradeoffs"],
        "must_avoid": ["false certainty"],
        "quality_criteria": ["State assumptions"],
        "critic_required": True,
    }


def apology_plan_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "understanding": {
            "user_goal": "Draft a professional apology email.",
            "intent": "draft generation",
            "task_type": "email drafting",
            "complexity": "simple",
            "ambiguity": "medium",
            "risk_level": "low",
            "risk_categories": [],
            "missing_information": ["recipient and incident details"],
            "assumptions": ["The user wants a respectful professional tone."],
            "uncertainties": ["The exact context of the apology is unspecified."],
            "concise_rationale": "The user is asking for a polished email draft.",
        },
        "clarification": {
            "action": "proceed",
            "question": None,
            "reason": (
                "A reusable apology email draft can be written with placeholders."
            ),
        },
        "strategy": "draft_generation",
        "worker_role": "worker",
        "output_contract": {
            "mode": "markdown",
            "structure": "professional email draft",
            "tone": "respectful and accountable",
            "length": "medium",
            "audience": "professional recipient",
        },
        "must_include": ["apology", "accountability", "next steps"],
        "must_avoid": ["defensiveness", "overexplaining"],
        "quality_criteria": ["Use a respectful tone.", "Keep the email concise."],
        "critic_required": True,
    }


def critic_pass_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "passes": True,
        "issues": [],
        "violated_criteria": [],
        "revision_recommended": False,
        "revision_instruction": None,
        "concise_summary": "The draft satisfies the plan.",
    }


def write_cli_config(
    tmp_path: Path,
    script: list[dict[str, object]],
    *,
    trace_enabled_by_default: bool = False,
    repair_attempts: int = 1,
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    script_path = tmp_path / "script.yaml"
    script_path.write_text(json.dumps(script), encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "providers": {
                    "scripted": {
                        "type": "mock",
                        "fixture_path": str(script_path),
                    }
                },
                "models": {
                    "scripted_general": {
                        "provider": "scripted",
                        "model": "scripted-model",
                    },
                    "scripted_revision": {
                        "provider": "scripted",
                        "model": "revision-model",
                    },
                },
                "roles": {
                    "understanding": "scripted_general",
                    "worker": "scripted_general",
                    "critic": "scripted_general",
                    "revision": "scripted_revision",
                },
                "runtime": {
                    "structured_output_repair_attempts": repair_attempts,
                    "trace": {
                        "enabled_by_default": trace_enabled_by_default,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return config_path


def cli(
    *args: str,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
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


def full_run_script() -> list[dict[str, object]]:
    return [
        {"expect": "understanding", "respond_json": plan_payload()},
        {"expect": "worker", "respond_text": "Draft answer."},
        {"expect": "critic", "respond_json": critic_pass_payload()},
    ]


def invalid_schema_understanding_script() -> list[dict[str, object]]:
    return [
        {
            "expect": "understanding",
            "respond_json": {
                "schema_version": 1,
                "understanding": {"summary": "unique_schema_raw_value"},
                "clarification": {"needs_clarification": False},
                "strategy": "draft_generation",
                "worker_role": "worker",
                "output_contract": {"format": "email"},
                "must_include": [],
                "must_avoid": [],
                "quality_criteria": [],
                "critic_required": True,
            },
        }
    ]


def test_run_default_prints_only_user_facing_result(tmp_path: Path) -> None:
    config_path = write_cli_config(tmp_path, full_run_script())

    result = cli(
        "run",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(config_path),
    )

    assert result.returncode == 0
    assert result.stdout == "Draft answer.\n"
    assert result.stderr == ""


def test_understand_show_llm_io_prints_request_and_raw_response(
    tmp_path: Path,
) -> None:
    config_path = write_cli_config(
        tmp_path,
        [{"expect": "understanding", "respond_json": plan_payload()}],
    )

    result = cli(
        "understand",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(config_path),
        "--show-llm-io",
    )

    assert result.returncode == 0
    assert "Status: understood" in result.stdout
    assert "===== LLM CALL: understanding =====" in result.stderr
    assert "Role: understanding" in result.stderr
    assert "Model: scripted_general" in result.stderr
    assert "Provider: scripted (mock)" in result.stderr
    assert "----- REQUEST MESSAGES -----" in result.stderr
    assert "[system]" in result.stderr
    assert "[user]" in result.stderr
    assert "----- RAW RESPONSE -----" in result.stderr
    assert "----- EXTRACTED JSON -----" in result.stderr


def test_understand_show_llm_io_prints_repair_call(tmp_path: Path) -> None:
    config_path = write_cli_config(
        tmp_path,
        [
            {
                "expect": "understanding",
                "respond_text": "not-json first_bad_response",
            },
            {"expect": "understanding", "respond_json": plan_payload()},
        ],
    )

    result = cli(
        "understand",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(config_path),
        "--show-llm-io",
    )

    assert result.returncode == 0
    assert "===== LLM CALL: understanding =====" in result.stderr
    assert "===== LLM CALL: understanding repair =====" in result.stderr
    assert "first_bad_response" in result.stderr
    assert "<INVALID_RESPONSE>" in result.stderr
    assert "----- VALIDATION ERROR -----" in result.stderr


def test_run_json_renders_final_response(tmp_path: Path) -> None:
    config_path = write_cli_config(tmp_path, full_run_script())

    result = cli(
        "run",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(config_path),
        "--json",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert payload["text"] == "Draft answer."
    assert payload["roles"] == {
        "understanding": "scripted_general",
        "worker": "scripted_general",
        "critic": "scripted_general",
        "revision": "scripted_revision",
    }


def test_run_show_llm_io_includes_multiple_stage_records(tmp_path: Path) -> None:
    config_path = write_cli_config(tmp_path, full_run_script())

    result = cli(
        "run",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(config_path),
        "--show-llm-io",
    )

    assert result.returncode == 0
    assert result.stdout == "Draft answer.\n"
    assert result.stderr.count("===== LLM CALL:") == 3
    assert "===== LLM CALL: understanding =====" in result.stderr
    assert "===== LLM CALL: worker =====" in result.stderr
    assert "===== LLM CALL: critic =====" in result.stderr


def test_run_with_trace_keeps_user_prompt_out_of_trace(tmp_path: Path) -> None:
    prompt = "Help me choose between SQLite and PostgreSQL."
    config_path = write_cli_config(tmp_path, full_run_script())

    result = cli("run", prompt, "--config", str(config_path), "--json", "--trace")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    trace = json.dumps(payload["trace"])
    assert "worker" in trace
    assert "OPENAI_API_KEY" not in trace
    assert prompt not in trace


def test_runtime_trace_default_includes_trace_without_cli_flag(tmp_path: Path) -> None:
    config_path = write_cli_config(
        tmp_path,
        full_run_script(),
        trace_enabled_by_default=True,
    )

    result = cli(
        "run",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(config_path),
        "--json",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["trace"]["events"]


def test_save_llm_io_writes_jsonl_file(tmp_path: Path) -> None:
    config_path = write_cli_config(tmp_path, full_run_script())
    output_path = tmp_path / "llm-io.jsonl"

    result = cli(
        "run",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(config_path),
        "--save-llm-io",
        str(output_path),
    )

    assert result.returncode == 0
    assert result.stdout == "Draft answer.\n"
    assert result.stderr == ""
    records = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["stage"] for record in records] == [
        "understanding",
        "worker",
        "critic",
    ]
    assert records[0]["request_messages"][0]["role"] == "system"
    assert records[0]["raw_response_text"]


def test_show_llm_io_does_not_change_pipeline_behavior(tmp_path: Path) -> None:
    normal_config = write_cli_config(tmp_path / "normal", full_run_script())
    debug_config = write_cli_config(tmp_path / "debug", full_run_script())

    normal = cli(
        "run",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(normal_config),
    )
    debug = cli(
        "run",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(debug_config),
        "--show-llm-io",
    )

    assert normal.returncode == debug.returncode == 0
    assert normal.stdout == debug.stdout == "Draft answer.\n"


def test_understand_json_renders_validated_plan(tmp_path: Path) -> None:
    config_path = write_cli_config(
        tmp_path,
        [{"expect": "understanding", "respond_json": plan_payload()}],
    )

    result = cli(
        "understand",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(config_path),
        "--json",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["plan"]["strategy"] == "comparison"
    assert payload["plan"]["worker_role"] == "worker"


def test_understand_professional_apology_email_with_correct_schema(
    tmp_path: Path,
) -> None:
    config_path = write_cli_config(
        tmp_path,
        [{"expect": "understanding", "respond_json": apology_plan_payload()}],
    )

    result = cli(
        "understand",
        "Help me write a professional apology email.",
        "--config",
        str(config_path),
        "--json",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["plan"]["strategy"] == "draft_generation"
    assert payload["plan"]["understanding"]["user_goal"] == (
        "Draft a professional apology email."
    )
    assert payload["plan"]["output_contract"]["mode"] == "markdown"


def test_schema_failure_debug_includes_raw_response_but_normal_does_not(
    tmp_path: Path,
) -> None:
    normal_config = write_cli_config(
        tmp_path / "normal",
        invalid_schema_understanding_script(),
        repair_attempts=0,
    )
    debug_config = write_cli_config(
        tmp_path / "debug",
        invalid_schema_understanding_script(),
        repair_attempts=0,
    )

    normal = cli(
        "understand",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(normal_config),
    )
    debug = cli(
        "understand",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(debug_config),
        "--show-llm-io",
    )

    assert normal.returncode == 5
    assert debug.returncode == 5
    assert "unique_schema_raw_value" not in normal.stderr
    assert "unique_schema_raw_value" in debug.stderr
    assert "----- VALIDATION ERROR -----" in debug.stderr


def test_plan_does_not_call_worker(tmp_path: Path) -> None:
    config_path = write_cli_config(
        tmp_path,
        [{"expect": "understanding", "respond_json": plan_payload()}],
    )

    result = cli(
        "plan",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(config_path),
        "--json",
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "planned"
    assert payload["prompt_plan"]["strategy"] == "comparison"
    assert "final_response" not in payload


def test_clarification_prints_single_question(tmp_path: Path) -> None:
    config_path = write_cli_config(
        tmp_path,
        [
            {
                "expect": "understanding",
                "respond_json": plan_payload(
                    action="ask_clarification",
                    question="What workload do you expect?",
                ),
            }
        ],
    )

    result = cli(
        "run",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(config_path),
    )

    assert result.returncode == 0
    assert result.stdout == "What workload do you expect?\n"


def test_stdin_supplies_prompt(tmp_path: Path) -> None:
    config_path = write_cli_config(tmp_path, full_run_script())

    result = cli(
        "run",
        "--stdin",
        "--config",
        str(config_path),
        stdin="Help me choose between SQLite and PostgreSQL.",
    )

    assert result.returncode == 0
    assert result.stdout == "Draft answer.\n"


def test_json_errors_are_stable_without_debug_traceback(tmp_path: Path) -> None:
    config_path = write_cli_config(tmp_path, [])

    result = cli("run", "--stdin", "--config", str(config_path), "--json", stdin="  ")

    assert result.returncode == 3
    payload: dict[str, Any] = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert payload["error"]["code"] == "INPUT_EMPTY"
    assert "Traceback" not in result.stderr


def test_unexpected_stack_traces_require_debug(tmp_path: Path) -> None:
    config_path = write_cli_config(tmp_path, [{"text": "{}"}])

    normal = cli(
        "run",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(config_path),
    )
    debug = cli(
        "run",
        "Help me choose between SQLite and PostgreSQL.",
        "--config",
        str(config_path),
        "--debug",
    )

    assert normal.returncode == 1
    assert "Unexpected internal error" in normal.stderr
    assert "Traceback" not in normal.stderr
    assert debug.returncode == 1
    assert "Traceback" in debug.stderr
