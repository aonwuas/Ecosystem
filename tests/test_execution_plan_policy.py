from __future__ import annotations

import pytest

from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import (
    ClarificationDecision,
    ExecutionPlan,
    OutputContract,
    PromptRequest,
    TaskUnderstanding,
)
from prompt_orchestrator.domain.enums import (
    AmbiguityLevel,
    ClarificationAction,
    ModelRole,
    OutputMode,
    RiskLevel,
    StrategyId,
    TaskComplexity,
)
from prompt_orchestrator.exceptions import ExecutionPlanValidationError, PolicyError
from prompt_orchestrator.policy import PolicyOutcome, evaluate_execution_plan_policy


def config_data(*, enable_critic: bool = True) -> dict[str, object]:
    return {
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
        "runtime": {
            "enable_critic": enable_critic,
        },
    }


def config(*, enable_critic: bool = True) -> PromptOrchestratorConfig:
    return PromptOrchestratorConfig.model_validate(
        config_data(enable_critic=enable_critic)
    )


def plan(
    *,
    strategy: StrategyId = StrategyId.COMPARISON,
    worker_role: ModelRole = ModelRole.WORKER,
    mode: OutputMode = OutputMode.MARKDOWN,
    action: ClarificationAction = ClarificationAction.PROCEED,
    question: str | None = None,
    risk_level: RiskLevel = RiskLevel.LOW,
    complexity: TaskComplexity = TaskComplexity.MODERATE,
    critic_required: bool = True,
    must_include: list[str] | None = None,
    missing_information: list[str] | None = None,
) -> ExecutionPlan:
    return ExecutionPlan(
        schema_version=1,
        understanding=TaskUnderstanding(
            user_goal="Choose the better option.",
            intent="decision support",
            task_type="comparison",
            complexity=complexity,
            ambiguity=AmbiguityLevel.MEDIUM,
            risk_level=risk_level,
            risk_categories=[],
            missing_information=missing_information or ["expected scale"],
            assumptions=[],
            uncertainties=[],
            concise_rationale="The user needs a comparison.",
        ),
        clarification=ClarificationDecision(
            action=action,
            question=question,
            reason="Enough information exists to proceed."
            if action is ClarificationAction.PROCEED
            else "The missing detail is required.",
        ),
        strategy=strategy,
        worker_role=worker_role,
        output_contract=OutputContract(
            mode=mode,
            structure="comparison",
            tone="practical",
            length="medium",
            audience="general user",
        ),
        must_include=must_include or ["tradeoffs"],
        must_avoid=["false certainty"],
        quality_criteria=["State assumptions"],
        critic_required=critic_required,
    )


def test_valid_proceed_plan_remains_semantically_intact() -> None:
    original = plan()

    evaluation = evaluate_execution_plan_policy(
        original,
        request=PromptRequest(prompt="Compare SQLite and PostgreSQL"),
        config=config(),
    )

    assert evaluation.outcome is PolicyOutcome.PROCEED
    assert evaluation.validated_plan.plan == original
    assert evaluation.validated_plan.policy_changes == []


def test_unregistered_strategy_cannot_execute() -> None:
    with pytest.raises(PolicyError, match="not registered"):
        evaluate_execution_plan_policy(
            plan(),
            request=PromptRequest(prompt="Compare options"),
            config=config(),
            registry={},
        )


def test_invalid_model_role_cannot_execute() -> None:
    invalid = plan().model_copy(update={"worker_role": "tool_runner"})

    with pytest.raises(ExecutionPlanValidationError, match="worker_role"):
        evaluate_execution_plan_policy(
            invalid,
            request=PromptRequest(prompt="Compare options"),
            config=config(),
        )


def test_specialist_model_role_is_forced_to_worker_role() -> None:
    evaluation = evaluate_execution_plan_policy(
        plan(worker_role=ModelRole.CRITIC),
        request=PromptRequest(prompt="Compare options"),
        config=config(),
    )

    assert evaluation.validated_plan.plan.worker_role is ModelRole.WORKER
    assert "worker_role changed from 'critic' to 'worker'" in (
        evaluation.validated_plan.policy_changes
    )


def test_caller_output_mode_override_takes_precedence_when_supported() -> None:
    evaluation = evaluate_execution_plan_policy(
        plan(mode=OutputMode.MARKDOWN),
        request=PromptRequest(prompt="Compare options", requested_output_mode="text"),
        config=config(),
    )

    assert evaluation.validated_plan.plan.output_contract.mode is OutputMode.TEXT
    assert evaluation.validated_plan.policy_changes == [
        "output_contract.mode changed from 'markdown' to caller-requested 'text'"
    ]


def test_unsupported_caller_output_mode_is_rejected() -> None:
    with pytest.raises(PolicyError, match="does not support"):
        evaluate_execution_plan_policy(
            plan(strategy=StrategyId.DIRECT_ANSWER),
            request=PromptRequest(
                prompt="Answer as JSON",
                requested_output_mode="json",
            ),
            config=config(),
        )


def test_model_selected_unsupported_output_mode_is_corrected() -> None:
    evaluation = evaluate_execution_plan_policy(
        plan(mode=OutputMode.JSON),
        request=PromptRequest(prompt="Compare options"),
        config=config(),
    )

    assert evaluation.validated_plan.plan.output_contract.mode is OutputMode.TEXT
    assert any(
        change.startswith("output_contract.mode changed to 'text'")
        for change in evaluation.validated_plan.policy_changes
    )


def test_high_risk_plan_cannot_disable_critic() -> None:
    evaluation = evaluate_execution_plan_policy(
        plan(risk_level=RiskLevel.HIGH, critic_required=False),
        request=PromptRequest(prompt="Give high-risk advice"),
        config=config(enable_critic=False),
    )

    assert evaluation.validated_plan.plan.critic_required is True
    assert "critic_required changed from false to true by policy" in (
        evaluation.validated_plan.policy_changes
    )


def test_low_risk_plan_can_follow_disabled_critic_runtime_policy() -> None:
    evaluation = evaluate_execution_plan_policy(
        plan(critic_required=True),
        request=PromptRequest(prompt="Write a limerick"),
        config=config(enable_critic=False),
    )

    assert evaluation.validated_plan.plan.critic_required is False
    assert "critic_required changed from true to false by runtime policy" in (
        evaluation.validated_plan.policy_changes
    )


def test_list_normalization_is_recorded() -> None:
    evaluation = evaluate_execution_plan_policy(
        plan(
            must_include=[" tradeoffs ", "Tradeoffs", "risks"],
            missing_information=["expected scale", "expected scale"],
        ),
        request=PromptRequest(prompt="Compare options"),
        config=config(),
    )

    assert evaluation.validated_plan.plan.must_include == ["tradeoffs", "risks"]
    assert "must_include normalized and deduplicated" in (
        evaluation.validated_plan.policy_changes
    )
    assert evaluation.validated_plan.plan.understanding.missing_information == [
        "expected scale"
    ]


def test_clarification_outcome_requires_one_focused_question() -> None:
    evaluation = evaluate_execution_plan_policy(
        plan(
            action=ClarificationAction.ASK_CLARIFICATION,
            question="  What source text should I summarize?  ",
        ),
        request=PromptRequest(prompt="Summarize it"),
        config=config(),
    )

    assert evaluation.outcome is PolicyOutcome.CLARIFICATION_REQUIRED
    assert (
        evaluation.validated_plan.plan.clarification.question
        == "What source text should I summarize?"
    )


def test_multi_question_clarification_is_rejected() -> None:
    with pytest.raises(PolicyError, match="only one focused question"):
        evaluate_execution_plan_policy(
            plan(
                action=ClarificationAction.ASK_CLARIFICATION,
                question="What source should I use? What length do you want?",
            ),
            request=PromptRequest(prompt="Summarize it"),
            config=config(),
        )


def test_refusal_outcome_is_preserved_without_worker_execution() -> None:
    evaluation = evaluate_execution_plan_policy(
        plan(
            strategy=StrategyId.SAFETY_REDIRECT,
            action=ClarificationAction.REFUSE_OR_REDIRECT,
            risk_level=RiskLevel.HIGH,
        ),
        request=PromptRequest(prompt="Unsafe request"),
        config=config(),
    )

    assert evaluation.outcome is PolicyOutcome.REFUSED
    assert (
        evaluation.validated_plan.plan.clarification.action
        is ClarificationAction.REFUSE_OR_REDIRECT
    )
