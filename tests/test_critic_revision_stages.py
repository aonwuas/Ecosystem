from __future__ import annotations

import json

import pytest

from prompt_orchestrator.clients import ScriptedModelClient
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import (
    ClarificationDecision,
    DraftResponse,
    ExecutionPlan,
    IntakeResult,
    OutputContract,
    PromptRequest,
    TaskUnderstanding,
)
from prompt_orchestrator.domain.enums import (
    AmbiguityLevel,
    ClarificationAction,
    CriticStatus,
    ModelRole,
    OutputMode,
    RiskLevel,
    StrategyId,
    TaskComplexity,
)
from prompt_orchestrator.exceptions import CriticError
from prompt_orchestrator.policy import evaluate_execution_plan_policy
from prompt_orchestrator.stages import run_critic_stage, run_quality_stage


def config(
    *,
    strict_critic: bool = False,
    enable_critic: bool = True,
    enable_revision: bool = True,
    repair_attempts: int = 1,
) -> PromptOrchestratorConfig:
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
                    "temperature": 0.2,
                    "max_output_tokens": 3000,
                    "timeout_seconds": 120,
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
                "strict_critic": strict_critic,
                "enable_critic": enable_critic,
                "enable_revision": enable_revision,
                "structured_output_repair_attempts": repair_attempts,
            },
        }
    )


def intake() -> IntakeResult:
    request = PromptRequest(
        prompt="Help me choose between SQLite and PostgreSQL.",
        context="The app starts small but may grow.",
    )
    return IntakeResult(
        request=request,
        normalized_prompt=request.prompt,
        normalized_context=request.context,
        warnings=[],
    )


def validated_plan():
    plan = ExecutionPlan(
        schema_version=1,
        understanding=TaskUnderstanding(
            user_goal="Choose the more appropriate database.",
            intent="decision support",
            task_type="comparison",
            complexity=TaskComplexity.MODERATE,
            ambiguity=AmbiguityLevel.MEDIUM,
            risk_level=RiskLevel.LOW,
            risk_categories=[],
            missing_information=["expected concurrency"],
            assumptions=["The application is early-stage."],
            uncertainties=["Expected concurrency is unknown."],
            concise_rationale="The user is comparing database options.",
        ),
        clarification=ClarificationDecision(
            action=ClarificationAction.PROCEED,
            question=None,
            reason="A conditional answer is useful.",
        ),
        strategy=StrategyId.COMPARISON,
        worker_role=ModelRole.WORKER,
        output_contract=OutputContract(
            mode=OutputMode.MARKDOWN,
            structure="comparison with recommendation",
            tone="practical",
            length="medium",
            audience="developer",
        ),
        must_include=["tradeoffs"],
        must_avoid=["false certainty"],
        quality_criteria=["State assumptions"],
        critic_required=True,
    )
    return evaluate_execution_plan_policy(
        plan,
        request=intake().request,
        config=config(),
    ).validated_plan


def draft(text: str = "SQLite is best.") -> DraftResponse:
    return DraftResponse(text=text, model_name="scripted_general", role="worker")


def critic_pass_json() -> str:
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


def critic_revision_json() -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "passes": False,
            "issues": [
                {
                    "code": "missing_assumption",
                    "severity": "major",
                    "message": "The draft omits assumptions.",
                    "criterion": "State assumptions",
                }
            ],
            "violated_criteria": ["State assumptions"],
            "revision_recommended": True,
            "revision_instruction": "Add explicit workload assumptions.",
            "concise_summary": "The draft is useful but incomplete.",
        }
    )


def test_critic_pass_returns_original_draft() -> None:
    client = ScriptedModelClient([{"expect": "critic", "text": critic_pass_json()}])

    result = run_quality_stage(
        intake=intake(),
        validated_plan=validated_plan(),
        draft=draft(),
        config=config(),
        client=client,
    )

    assert result.draft == draft()
    assert result.quality.status is CriticStatus.PASSED
    assert result.revision_performed is False
    assert len(client.requests) == 1
    assert client.requests[0].request_kind == "critic"
    assert "<DRAFT>" in client.requests[0].messages[1].content
    assert "State assumptions" in client.requests[0].messages[1].content


def test_invalid_critic_output_is_repaired_once() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "critic", "text": '{"bad": true}'},
            {"expect": "critic", "text": critic_pass_json()},
        ]
    )

    result = run_critic_stage(
        intake=intake(),
        validated_plan=validated_plan(),
        draft=draft(),
        config=config(),
        client=client,
    )

    assert result.quality.status is CriticStatus.PASSED
    assert len(client.requests) == 2
    assert "<INVALID_RESPONSE>" in client.requests[1].messages[1].content


def test_critic_failure_degrades_when_non_strict() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "critic", "text": '{"bad": true}'},
            {"expect": "critic", "text": '{"still": "bad"}'},
        ]
    )

    result = run_quality_stage(
        intake=intake(),
        validated_plan=validated_plan(),
        draft=draft(),
        config=config(strict_critic=False),
        client=client,
    )

    assert result.draft == draft()
    assert result.quality.status is CriticStatus.NOT_CHECKED
    assert result.warnings == ["critic review failed; draft was not checked"]


def test_critic_failure_raises_when_strict() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "critic", "text": '{"bad": true}'},
            {"expect": "critic", "text": '{"still": "bad"}'},
        ]
    )

    with pytest.raises(CriticError, match="Critic review failed"):
        run_quality_stage(
            intake=intake(),
            validated_plan=validated_plan(),
            draft=draft(),
            config=config(strict_critic=True),
            client=client,
        )


def test_revision_recommendation_produces_revised_draft_once() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "critic", "text": critic_revision_json()},
            {"expect": "revision", "text": "Revised answer with assumptions."},
        ]
    )

    result = run_quality_stage(
        intake=intake(),
        validated_plan=validated_plan(),
        draft=draft(),
        config=config(),
        client=client,
    )

    assert result.draft.text == "Revised answer with assumptions."
    assert result.draft.model_name == "scripted_revision"
    assert result.draft.role is ModelRole.REVISION
    assert result.revision_performed is True
    assert [request.request_kind for request in client.requests] == [
        "critic",
        "revision",
    ]
    assert "<REVISION_INSTRUCTION>" in client.requests[1].messages[1].content


def test_revision_failure_preserves_original_draft() -> None:
    original = draft()
    client = ScriptedModelClient(
        [
            {"expect": "critic", "text": critic_revision_json()},
            {"expect": "revision", "text": "   "},
        ]
    )

    result = run_quality_stage(
        intake=intake(),
        validated_plan=validated_plan(),
        draft=original,
        config=config(),
        client=client,
    )

    assert result.draft == original
    assert result.revision_performed is False
    assert result.warnings
    assert "original draft preserved" in result.warnings[0]


def test_revision_disabled_preserves_original_without_calling_revision() -> None:
    original = draft()
    client = ScriptedModelClient([{"expect": "critic", "text": critic_revision_json()}])

    result = run_quality_stage(
        intake=intake(),
        validated_plan=validated_plan(),
        draft=original,
        config=config(enable_revision=False),
        client=client,
    )

    assert result.draft == original
    assert result.revision_performed is False
    assert len(client.requests) == 1
    assert result.warnings == ["revision skipped by runtime policy"]
