from __future__ import annotations

import json
from pathlib import Path

from prompt_orchestrator import cli
from prompt_orchestrator.clients import ScriptedModelClient


def _config_path(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "providers": {"scripted": {"type": "mock", "fixture_path": "x"}},
                "models": {
                    "scripted_general": {
                        "provider": "scripted",
                        "model": "scripted-model",
                    }
                },
                "roles": {
                    "understanding": "scripted_general",
                    "worker": "scripted_general",
                    "critic": "scripted_general",
                    "revision": "scripted_general",
                },
                "runtime": {},
            }
        ),
        encoding="utf-8",
    )
    return path


def _plan_json() -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "understanding": {
                "user_goal": "Choose a database.",
                "intent": "decision support",
                "task_type": "comparison",
                "complexity": "moderate",
                "ambiguity": "medium",
                "risk_level": "low",
                "risk_categories": [],
                "missing_information": [],
                "assumptions": [],
                "uncertainties": [],
                "concise_rationale": "The user is comparing database options.",
            },
            "clarification": {
                "action": "proceed",
                "question": None,
                "reason": "A conditional answer can proceed.",
            },
            "strategy": "comparison",
            "output_contract": {
                "mode": "markdown",
                "structure": "comparison",
                "tone": "practical",
                "length": "medium",
                "audience": "developer",
            },
            "must_include": [],
            "must_avoid": [],
            "quality_criteria": [],
            "critic_required": True,
        }
    )


def test_cli_closes_client_after_successful_command(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    client = ScriptedModelClient([{"expect": "understanding", "text": _plan_json()}])
    monkeypatch.setattr(cli, "create_pipeline_client", lambda config: client)

    exit_code = cli.main(
        [
            "understand",
            "Help me choose between SQLite and PostgreSQL.",
            "--config",
            str(_config_path(tmp_path)),
        ]
    )

    capsys.readouterr()
    assert exit_code == 0
    assert client.close_count == 1


def test_cli_closes_client_after_controlled_input_error(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    client = ScriptedModelClient([])
    monkeypatch.setattr(cli, "create_pipeline_client", lambda config: client)

    exit_code = cli.main(["run", "--config", str(_config_path(tmp_path))])

    capsys.readouterr()
    assert exit_code == 3
    assert client.close_count == 1
