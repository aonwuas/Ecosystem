"""Tests for the evaluation harness, corpus loading, checks, and judge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from prompt_orchestrator.clients import ScriptedModelClient
from prompt_orchestrator.clients.mock import ScriptedResponse
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import FinalResponse, PromptRequest, RunUsage
from prompt_orchestrator.domain.enums import CriticStatus, PipelineStatus
from prompt_orchestrator.evaluation import (
    ArmSpec,
    EvalChecks,
    EvalCorpus,
    evaluate_checks,
    load_corpus,
    run_evaluation,
)
from prompt_orchestrator.evaluation.corpus import EvalCase
from prompt_orchestrator.exceptions import InputError
from prompt_orchestrator.pipeline import PipelineRunner


def config() -> PromptOrchestratorConfig:
    return PromptOrchestratorConfig.model_validate(
        {
            "version": 1,
            "providers": {
                "scripted": {
                    "type": "mock",
                    "fixture_path": "tests/fixtures/scripted_models.yaml",
                }
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
    )


def _plan_json(strategy: str = "comparison") -> str:
    return json.dumps(
        {
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
            "strategy": strategy,
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
    )


def _critic_pass_json() -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "passes": True,
            "issues": [],
            "violated_criteria": [],
            "revision_recommended": False,
            "revision_instruction": None,
            "concise_summary": "The draft satisfies the plan.",
        }
    )


def _one_case_corpus() -> EvalCorpus:
    return EvalCorpus(
        cases=[
            EvalCase(
                id="db",
                prompt="Compare SQLite and PostgreSQL.",
                category="comparison",
                rubric="Prefer the answer that states assumptions.",
                checks=EvalChecks(must_include=["postgresql"], min_length=10),
            )
        ]
    )


# --- checks -------------------------------------------------------------------


def _final(
    text: str, status: PipelineStatus = PipelineStatus.COMPLETED
) -> FinalResponse:
    return FinalResponse.model_validate(
        {
            "status": status,
            "text": text,
            "roles": {
                "understanding": "m",
                "worker": "m",
                "critic": "m",
                "revision": "m",
            },
            "critic_status": CriticStatus.PASSED,
            "revision_performed": False,
            "used_safe_fallback": False,
        }
    )


def test_checks_pass_and_fail() -> None:
    response = _final("PostgreSQL scales well; SQLite is simple.")
    ok = evaluate_checks(response, EvalChecks(must_include=["postgresql"]))
    assert ok.passed is True

    bad = evaluate_checks(
        response,
        EvalChecks(must_include=["mysql"], must_avoid=["sqlite"], min_length=1000),
    )
    assert bad.passed is False
    assert len(bad.failures) == 3


def test_checks_expect_status() -> None:
    response = FinalResponse.model_validate(
        {
            "status": PipelineStatus.CLARIFICATION_REQUIRED,
            "text": "",
            "clarification_question": "Which database workload do you expect?",
            "roles": {
                "understanding": "m",
                "worker": "m",
                "critic": "m",
                "revision": "m",
            },
            "critic_status": CriticStatus.SKIPPED,
            "revision_performed": False,
            "used_safe_fallback": False,
        }
    )
    # The clarification question is used as the answer for content checks.
    outcome = evaluate_checks(
        response,
        EvalChecks(
            expect_status=PipelineStatus.CLARIFICATION_REQUIRED,
            must_include=["workload"],
        ),
    )
    assert outcome.passed is True


# --- corpus loading -----------------------------------------------------------


def test_load_corpus_from_file(tmp_path: Path) -> None:
    corpus_file = tmp_path / "corpus.yaml"
    corpus_file.write_text(
        "cases:\n"
        "  - id: a\n"
        "    prompt: Do a thing.\n"
        "    checks:\n"
        "      must_include: [thing]\n",
        encoding="utf-8",
    )
    corpus = load_corpus(corpus_file)
    assert len(corpus.cases) == 1
    assert corpus.cases[0].id == "a"


def test_load_corpus_rejects_duplicate_ids(tmp_path: Path) -> None:
    corpus_file = tmp_path / "corpus.yaml"
    corpus_file.write_text(
        "- id: a\n  prompt: One.\n- id: a\n  prompt: Two.\n",
        encoding="utf-8",
    )
    with pytest.raises(InputError):
        load_corpus(corpus_file)


def test_load_corpus_missing_path(tmp_path: Path) -> None:
    with pytest.raises(InputError):
        load_corpus(tmp_path / "nope.yaml")


# --- baseline -----------------------------------------------------------------


def test_run_baseline_single_call() -> None:
    client = ScriptedModelClient(
        [ScriptedResponse(expect="baseline", text="A direct single-call answer.")]
    )
    runner = PipelineRunner(config=config(), client=client)
    response = runner.run_baseline(PromptRequest(prompt="Answer me."))
    assert response.status is PipelineStatus.COMPLETED
    assert response.text == "A direct single-call answer."
    assert client.remaining == 0


# --- harness ------------------------------------------------------------------


def test_run_evaluation_compares_arms_with_cost() -> None:
    client = ScriptedModelClient(
        [
            ScriptedResponse(
                expect="understanding", text=_plan_json(), total_tokens=500
            ),
            ScriptedResponse(
                expect="worker",
                text="PostgreSQL scales; SQLite is simple. Assumptions stated.",
                total_tokens=700,
            ),
            ScriptedResponse(
                expect="critic", text=_critic_pass_json(), total_tokens=400
            ),
            ScriptedResponse(
                expect="baseline",
                text="PostgreSQL vs SQLite: pick per scale.",
                total_tokens=300,
            ),
        ]
    )
    report = run_evaluation(
        corpus=_one_case_corpus(),
        config=config(),
        client=client,
        arm_spec=ArmSpec(controls=("single_call",)),
        judge=False,
    )
    assert report.case_count == 1
    assert report.treatment == "orchestrated"
    assert report.arms["orchestrated"].passes == 1
    assert report.arms["single_call"].passes == 1
    assert report.arms["orchestrated"].total_tokens == 1600
    assert report.arms["single_call"].total_tokens == 300
    assert report.arms["orchestrated"].calls == 3
    assert report.arms["single_call"].calls == 1
    # The single-call control's compute ratio vs treatment is visible for fairness.
    assert report.arms["single_call"].compute_ratio_vs_treatment == pytest.approx(
        300 / 1600
    )
    assert report.arms["orchestrated"].compute_ratio_vs_treatment is None
    case = report.cases[0]
    assert isinstance(case.arms["orchestrated"].usage, RunUsage)


def test_run_evaluation_no_controls() -> None:
    client = ScriptedModelClient(
        [
            ScriptedResponse(expect="understanding", text=_plan_json()),
            ScriptedResponse(
                expect="worker", text="PostgreSQL and SQLite compared here."
            ),
            ScriptedResponse(expect="critic", text=_critic_pass_json()),
        ]
    )
    report = run_evaluation(
        corpus=_one_case_corpus(),
        config=config(),
        client=client,
        arm_spec=ArmSpec(controls=()),
        judge=False,
    )
    assert list(report.arms) == ["orchestrated"]
    assert report.comparisons == {}
    assert client.remaining == 0


def test_run_evaluation_with_judge_both_orders() -> None:
    # Both orders must agree for a decisive winner. Treatment is slot A in order 1
    # and slot B in order 2, so "a" then "b" both mean the treatment won.
    judge_order1 = json.dumps(
        {"winner": "a", "confidence": 4, "reason": "A is more complete."}
    )
    judge_order2 = json.dumps(
        {"winner": "b", "confidence": 5, "reason": "B is more complete."}
    )
    client = ScriptedModelClient(
        [
            ScriptedResponse(expect="understanding", text=_plan_json()),
            ScriptedResponse(
                expect="worker", text="PostgreSQL and SQLite, with assumptions."
            ),
            ScriptedResponse(expect="critic", text=_critic_pass_json()),
            ScriptedResponse(expect="baseline", text="PostgreSQL or SQLite, briefly."),
            ScriptedResponse(expect="judge", text=judge_order1),
            ScriptedResponse(expect="judge", text=judge_order2),
        ]
    )
    report = run_evaluation(
        corpus=_one_case_corpus(),
        config=config(),
        client=client,
        arm_spec=ArmSpec(controls=("single_call",)),
        judge=True,
    )
    verdict = report.cases[0].judgements["single_call"]
    assert verdict.winner == "treatment"
    assert verdict.order_consistent is True
    assert report.comparisons["single_call"].judge_treatment_wins == 1
    assert client.remaining == 0
