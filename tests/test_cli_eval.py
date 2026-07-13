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
    assert report["treatment"] == "orchestrated"
    assert report["arms"]["orchestrated"]["passes"] == 1
    assert report["arms"]["single_call"]["passes"] == 1
    assert report["arms"]["orchestrated"]["total_tokens"] == 1600
    assert report["arms"]["single_call"]["total_tokens"] == 300
    assert report["arms"]["orchestrated"]["calls"] == 3
    assert report["arms"]["single_call"]["calls"] == 1
    assert report["comparisons"]["single_call"]["mcnemar_p"] == 1.0


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
    assert "Treatment vs controls" in result.stdout
    assert "x tokens" in result.stdout


def test_eval_none_arms_skips_controls(tmp_path: Path) -> None:
    script = _eval_script()[:3]  # understanding, worker, critic only
    config_path = _write_config(tmp_path, script)
    corpus_path = _write_corpus(tmp_path)

    result = cli(
        "eval",
        "--config",
        str(config_path),
        "--corpus",
        str(corpus_path),
        "--arms",
        "none",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert list(report["arms"]) == ["orchestrated"]
    assert report["comparisons"] == {}


def test_eval_best_of_n_and_self_refine_arms(tmp_path: Path) -> None:
    # Per case: orchestrated (understanding, worker, critic), then best_of_2
    # (2 candidates + 1 selection), then self_refine (draft + revise).
    script: list[dict[str, object]] = [
        {
            "expect": "understanding",
            "respond_json": _plan_payload(),
            "total_tokens": 500,
        },
        {
            "expect": "worker",
            "respond_text": "PostgreSQL vs SQLite.",
            "total_tokens": 700,
        },
        {
            "expect": "critic",
            "respond_json": _critic_pass_payload(),
            "total_tokens": 400,
        },
        {
            "expect": "candidate",
            "respond_text": "PostgreSQL option one.",
            "total_tokens": 250,
        },
        {
            "expect": "candidate",
            "respond_text": "PostgreSQL option two.",
            "total_tokens": 260,
        },
        {
            "expect": "selection",
            "respond_json": {"best_index": 1, "reason": "clearer"},
            "total_tokens": 120,
        },
        {
            "expect": "self_refine_draft",
            "respond_text": "PostgreSQL draft.",
            "total_tokens": 200,
        },
        {
            "expect": "self_refine_revise",
            "respond_text": "PostgreSQL improved.",
            "total_tokens": 220,
        },
    ]
    config_path = _write_config(tmp_path, script)
    corpus_path = _write_corpus(tmp_path)

    result = cli(
        "eval",
        "--config",
        str(config_path),
        "--corpus",
        str(corpus_path),
        "--arms",
        "best_of_n,self_refine",
        "--best-of-n",
        "2",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert set(report["arms"]) == {"orchestrated", "best_of_2", "self_refine"}
    # best_of_2 = 2 candidates + 1 selection = 3 calls; self_refine = 2 calls.
    assert report["arms"]["best_of_2"]["calls"] == 3
    assert report["arms"]["self_refine"]["calls"] == 2
    assert report["arms"]["best_of_2"]["total_tokens"] == 630
    # Selected candidate index 1 ("option two") is the returned answer.
    assert "option two" in report["cases"][0]["arms"]["best_of_2"]["answer_preview"]


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
