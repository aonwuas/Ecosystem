from __future__ import annotations

import pytest

from prompt_orchestrator.clients import ScriptedModelClient
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import (
    ClarificationDecision,
    ExecutionPlan,
    IntakeResult,
    OutputContract,
    PromptRequest,
    TaskUnderstanding,
    ValidatedExecutionPlan,
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
from prompt_orchestrator.exceptions import PolicyError, WorkerError
from prompt_orchestrator.policy import evaluate_execution_plan_policy
from prompt_orchestrator.stages import build_worker_prompt_plan, run_worker_stage


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
                "scripted_understanding": {
                    "provider": "scripted",
                    "model": "understanding-model",
                },
                "scripted_worker": {
                    "provider": "scripted",
                    "model": "worker-model",
                    "temperature": 0.3,
                    "max_output_tokens": 2048,
                    "timeout_seconds": 120,
                },
            },
            "roles": {
                "understanding": "scripted_understanding",
                "worker": "scripted_worker",
                "critic": "scripted_worker",
                "revision": "scripted_worker",
            },
        }
    )


def intake() -> IntakeResult:
    request = PromptRequest(
        prompt="Help me choose between SQLite and PostgreSQL.",
        context="The app starts small but may gain teams later.",
    )
    return IntakeResult(
        request=request,
        normalized_prompt=request.prompt,
        normalized_context=request.context,
        warnings=[],
    )


def execution_plan(
    *,
    strategy: StrategyId = StrategyId.COMPARISON,
    action: ClarificationAction = ClarificationAction.PROCEED,
    question: str | None = None,
    mode: OutputMode = OutputMode.MARKDOWN,
) -> ExecutionPlan:
    return ExecutionPlan(
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
            action=action,
            question=question,
            reason="A conditional answer is useful."
            if action is ClarificationAction.PROCEED
            else "A required detail is missing.",
        ),
        strategy=strategy,
        worker_role=ModelRole.WORKER,
        output_contract=OutputContract(
            mode=mode,
            structure="comparison with recommendation",
            tone="practical and neutral",
            length="medium",
            audience="software developer",
        ),
        must_include=["tradeoffs", "conditional recommendation"],
        must_avoid=["pretending missing requirements are known"],
        quality_criteria=["State assumptions"],
        critic_required=True,
    )


def validated_plan(
    *,
    strategy: StrategyId = StrategyId.COMPARISON,
    action: ClarificationAction = ClarificationAction.PROCEED,
    question: str | None = None,
    mode: OutputMode = OutputMode.MARKDOWN,
) -> ValidatedExecutionPlan:
    evaluation = evaluate_execution_plan_policy(
        execution_plan(
            strategy=strategy,
            action=action,
            question=question,
            mode=mode,
        ),
        request=intake().request,
        config=config(),
    )
    return evaluation.validated_plan


def test_prompt_plan_uses_strategy_template_and_caller_context() -> None:
    prompt_plan = build_worker_prompt_plan(
        intake=intake(),
        validated_plan=validated_plan(),
    )

    assert prompt_plan.strategy is StrategyId.COMPARISON
    assert prompt_plan.worker_role is ModelRole.WORKER
    assert "Compare options on explicit criteria" in prompt_plan.user_prompt
    assert "comparison with recommendation" in prompt_plan.user_prompt
    assert "tradeoffs" in prompt_plan.user_prompt
    assert "State assumptions" in prompt_plan.user_prompt
    assert (
        "<USER_REQUEST>\nHelp me choose between SQLite and PostgreSQL.\n</USER_REQUEST>"
    ) in prompt_plan.user_prompt
    assert (
        "<CALLER_CONTEXT>\nThe app starts small but may gain teams later.\n"
        "</CALLER_CONTEXT>"
    ) in prompt_plan.user_prompt


def test_user_content_appears_only_inside_delimiters() -> None:
    prompt_plan = build_worker_prompt_plan(
        intake=intake(),
        validated_plan=validated_plan(strategy=StrategyId.DIRECT_ANSWER),
    )

    user_text = "Help me choose between SQLite and PostgreSQL."
    assert prompt_plan.user_prompt.count(user_text) == 1
    assert f"<USER_REQUEST>\n{user_text}\n</USER_REQUEST>" in (prompt_plan.user_prompt)
    assert user_text not in prompt_plan.system_prompt


def test_structured_output_strategy_inserts_json_contract() -> None:
    structured_intake = intake()
    request = structured_intake.request.model_copy(
        update={"requested_output_mode": OutputMode.JSON}
    )
    structured_intake = IntakeResult(
        request=request,
        normalized_prompt=structured_intake.normalized_prompt,
        normalized_context=structured_intake.normalized_context,
        warnings=[],
    )
    evaluation = evaluate_execution_plan_policy(
        execution_plan(strategy=StrategyId.STRUCTURED_OUTPUT, mode=OutputMode.JSON),
        request=request,
        config=config(),
    )

    prompt_plan = build_worker_prompt_plan(
        intake=structured_intake,
        validated_plan=evaluation.validated_plan,
    )

    assert prompt_plan.output_contract.mode is OutputMode.JSON
    assert "Return output that conforms" in prompt_plan.user_prompt
    assert '"mode":"json"' in prompt_plan.user_prompt


def test_plan_operation_does_not_call_worker_client() -> None:
    client = ScriptedModelClient([{"expect": "worker", "text": "Draft"}])

    build_worker_prompt_plan(
        intake=intake(),
        validated_plan=validated_plan(),
    )

    assert client.requests == []


def test_worker_stage_calls_worker_role_and_returns_draft_response() -> None:
    client = ScriptedModelClient([{"expect": "worker", "text": " Draft answer.  "}])

    result = run_worker_stage(
        intake=intake(),
        validated_plan=validated_plan(),
        config=config(),
        client=client,
    )

    assert result.draft.text == "Draft answer."
    assert result.draft.model_name == "scripted_worker"
    assert result.draft.role is ModelRole.WORKER
    assert client.requests[0].role is ModelRole.WORKER
    assert client.requests[0].model_name == "scripted_worker"
    assert client.requests[0].temperature == 0.3
    assert client.requests[0].request_kind == "worker"
    assert client.requests[0].messages[0].role == "system"
    assert client.requests[0].messages[1].content == result.prompt_plan.user_prompt


def test_empty_worker_output_fails_clearly() -> None:
    client = ScriptedModelClient([{"expect": "worker", "text": "   "}])

    with pytest.raises(WorkerError, match="empty"):
        run_worker_stage(
            intake=intake(),
            validated_plan=validated_plan(),
            config=config(),
            client=client,
        )


def test_clarification_plan_never_calls_worker() -> None:
    client = ScriptedModelClient([{"expect": "worker", "text": "Draft"}])

    with pytest.raises(PolicyError, match="Clarification"):
        run_worker_stage(
            intake=intake(),
            validated_plan=validated_plan(
                action=ClarificationAction.ASK_CLARIFICATION,
                question="What workload do you expect?",
            ),
            config=config(),
            client=client,
        )

    assert client.requests == []


def test_refusal_plan_never_calls_worker() -> None:
    client = ScriptedModelClient([{"expect": "worker", "text": "Draft"}])

    with pytest.raises(PolicyError, match="Refusal"):
        run_worker_stage(
            intake=intake(),
            validated_plan=validated_plan(
                strategy=StrategyId.SAFETY_REDIRECT,
                action=ClarificationAction.REFUSE_OR_REDIRECT,
            ),
            config=config(),
            client=client,
        )

    assert client.requests == []
