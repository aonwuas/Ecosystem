"""End-to-end CLI tests for `eval` and run-level cost visibility."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _plan_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "understanding": {
            "user_goal": "Choose the more appropriate database.",
            "intent": "decision support",
            "task_type": "comparison",
            "complexity": "moderate",
            "ambiguity": "low",
            "risk_level": "low",
            "risk_categories": [],
            "missing_information": [],
            "assumptions": ["The application is early-stage."],
            "uncertainties": [],
            "concise_rationale": "The user is comparing options.",
        },
        "clarification": {
            "action": "proceed",
            "question": None,
            "reason": "A conditional answer is useful.",
        },
        "strategy": "comparison",
        "output_contract": {
            "mode": "markdown",
            "structure": "comparison",
            "tone": "practical",
            "length": "medium",
            "audience": "developer",
        },
        "must_include": ["tradeoffs"],
        "must_avoid": ["false certainty"],
        "quality_criteria": ["State assumptions"],
        "critic_required": True,
    }


def _critic_pass_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "passes": True,
        "issues": [],
        "violated_criteria": [],
        "revision_recommended": False,
        "revision_instruction": None,
        "concise_summary": "The draft satisfies the plan.",
    }


def _write_config(tmp_path: Path, script: list[dict[str, object]]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    script_path = tmp_path / "script.yaml"
    script_path.write_text(json.dumps(script), encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "providers": {
                    "scripted": {"type": "mock", "fixture_path": str(script_path)}
                },
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
            }
        ),
        encoding="utf-8",
    )
    return config_path


def _write_corpus(tmp_path: Path) -> Path:
    corpus_path = tmp_path / "corpus.yaml"
    corpus_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "db",
                        "prompt": "Compare SQLite and PostgreSQL.",
                        "category": "comparison",
                        "checks": {"must_include": ["postgresql"], "min_length": 10},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return corpus_path


def cli(*args: str) -> subprocess.CompletedProcess[str]:
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
        text=True,
        capture_output=True,
        check=False,
    )


def _eval_script() -> list[dict[str, object]]:
    return [
        {
            "expect": "understanding",
            "respond_json": _plan_payload(),
            "total_tokens": 500,
        },
        {
            "expect": "worker",
            "respond_text": "PostgreSQL scales; SQLite is simple. Assumptions stated.",
            "total_tokens": 700,
        },
        {
            "expect": "critic",
            "respond_json": _critic_pass_payload(),
            "total_tokens": 400,
        },
        {
            "expect": "baseline",
            "respond_text": "PostgreSQL vs SQLite, briefly.",
            "total_tokens": 300,
        },
    ]


def test_eval_json_reports_arms_and_cost(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, _eval_script())
    corpus_path = _write_corpus(tmp_path)

    result = cli(
        "eval",
        "--config",
        str(config_path),
        "--corpus",
        str(corpus_path),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["case_count"] == 1
    assert report["orchestrated_passes"] == 1
    assert report["baseline_passes"] == 1
    assert report["orchestrated_total_tokens"] == 1600
    assert report["baseline_total_tokens"] == 300
    assert report["orchestrated_calls"] == 3
    assert report["baseline_calls"] == 1


def test_eval_text_report_includes_cost_premium(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, _eval_script())
    corpus_path = _write_corpus(tmp_path)

    result = cli(
        "eval",
        "--config",
        str(config_path),
        "--corpus",
        str(corpus_path),
    )

    assert result.returncode == 0, result.stderr
    assert "Evaluation report" in result.stdout
    assert "token cost premium" in result.stdout


def test_eval_no_baseline_skips_baseline_arm(tmp_path: Path) -> None:
    script = _eval_script()[:3]  # understanding, worker, critic only
    config_path = _write_config(tmp_path, script)
    corpus_path = _write_corpus(tmp_path)

    result = cli(
        "eval",
        "--config",
        str(config_path),
        "--corpus",
        str(corpus_path),
        "--no-baseline",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["baseline_passes"] is None
    assert report["cases"][0]["baseline"] is None


def test_run_json_includes_usage(tmp_path: Path) -> None:
    script: list[dict[str, object]] = [
        {
            "expect": "understanding",
            "respond_json": _plan_payload(),
            "total_tokens": 500,
        },
        {"expect": "worker", "respond_text": "Draft answer.", "total_tokens": 700},
        {
            "expect": "critic",
            "respond_json": _critic_pass_payload(),
            "total_tokens": 400,
        },
    ]
    config_path = _write_config(tmp_path, script)

    result = cli(
        "run",
        "Compare SQLite and PostgreSQL.",
        "--config",
        str(config_path),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["usage"]["call_count"] == 3
    assert payload["usage"]["total_tokens"] == 1600
