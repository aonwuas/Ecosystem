from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from prompt_orchestrator.domain import (
    ClarificationDecision,
    CriticIssue,
    CriticResult,
    DraftResponse,
    ExecutionPlan,
    FinalResponse,
    IntakeResult,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    PromptPlan,
    PromptRequest,
    QualityResult,
    RoleModelNames,
    TaskUnderstanding,
    Trace,
    TraceEvent,
    ValidatedExecutionPlan,
)
from prompt_orchestrator.domain.enums import (
    CriticIssueSeverity,
    CriticStatus,
    ModelRole,
    PipelineStatus,
)


def example_execution_plan_data() -> dict[str, object]:
    return {
        "schema_version": 1,
        "understanding": {
            "user_goal": "Choose the more appropriate database",
            "intent": "decision support",
            "task_type": "comparison",
            "complexity": "moderate",
            "ambiguity": "medium",
            "risk_level": "low",
            "risk_categories": [],
            "missing_information": ["expected concurrency", "deployment environment"],
            "assumptions": [],
            "uncertainties": ["The scale of the application is unspecified"],
            "concise_rationale": "The user is comparing two technologies.",
        },
        "clarification": {
            "action": "proceed",
            "question": None,
            "reason": "A useful conditional comparison can be provided.",
        },
        "strategy": "comparison",
        "output_contract": {
            "mode": "markdown",
            "structure": "comparison with recommendation",
            "tone": "practical and neutral",
            "length": "medium",
            "audience": "software developer",
        },
        "must_include": ["tradeoffs", "conditional recommendation"],
        "must_avoid": ["pretending missing scale requirements are known"],
        "quality_criteria": [
            "Distinguish embedded/local use from client-server use",
            "State assumptions",
            "Give a recommendation conditional on expected workload",
        ],
        "critic_required": True,
    }


def test_documented_request_and_intake_examples_validate() -> None:
    request = PromptRequest.model_validate(
        {
            "prompt": "Help me choose between SQLite and PostgreSQL",
            "context": None,
            "requested_output_mode": None,
            "conversation_id": None,
            "metadata": {},
        }
    )
    intake = IntakeResult(
        request=request,
        normalized_prompt="Help me choose between SQLite and PostgreSQL",
        normalized_context=None,
        warnings=[],
    )

    assert request.prompt == "Help me choose between SQLite and PostgreSQL"
    assert json.loads(intake.model_dump_json())["warnings"] == []


def test_documented_execution_plan_example_validates_and_serializes() -> None:
    plan = ExecutionPlan.model_validate(example_execution_plan_data())
    validated_plan = ValidatedExecutionPlan(plan=plan)

    serialized = json.loads(validated_plan.model_dump_json())

    assert serialized["plan"]["strategy"] == "comparison"
    assert "worker_role" not in serialized["plan"]
    assert serialized["used_safe_fallback"] is False


def test_provider_neutral_model_io_examples_validate() -> None:
    request = ModelRequest(
        role="worker",
        model_name="local_general",
        messages=[
            ModelMessage(role="system", content="System prompt"),
            ModelMessage(role="user", content="User prompt"),
        ],
        temperature=0.2,
        max_output_tokens=4096,
        timeout_seconds=180,
        request_kind="worker",
    )
    response = ModelResponse(
        text="Draft answer",
        model="server-returned-model",
        finish_reason="stop",
        usage={"input_tokens": None, "output_tokens": None, "total_tokens": None},
        provider_metadata={},
    )

    assert request.role is ModelRole.WORKER
    assert json.loads(response.model_dump_json())["finish_reason"] == "stop"


def test_draft_critic_quality_final_and_trace_examples_validate() -> None:
    plan = ExecutionPlan.model_validate(example_execution_plan_data())
    prompt_plan = PromptPlan(
        strategy=plan.strategy,
        worker_role=ModelRole.WORKER,
        system_prompt="System prompt",
        user_prompt="User prompt",
        output_contract=plan.output_contract,
        quality_criteria=[],
    )
    draft = DraftResponse(
        text="Draft answer", model_name="local_general", role="worker"
    )
    critic = CriticResult(
        schema_version=1,
        passes=False,
        issues=[
            CriticIssue(
                code="missing_constraint",
                severity="major",
                message="The draft does not state its assumptions.",
                criterion="State assumptions",
            )
        ],
        violated_criteria=["State assumptions"],
        revision_recommended=True,
        revision_instruction="Add explicit workload assumptions.",
        concise_summary="The answer is useful but overconfident.",
    )
    quality = QualityResult(status="revision_recommended", critic_result=critic)
    trace = Trace(
        events=[
            TraceEvent(
                stage="critic",
                event="reviewed",
                status="ok",
                duration_ms=1.5,
                attempt=1,
                details={"model": "local_general"},
            )
        ]
    )
    final = FinalResponse(
        status="completed",
        text="Final answer",
        clarification_question=None,
        strategy="comparison",
        roles=RoleModelNames(
            understanding="local_general",
            worker="local_general",
            critic="local_general",
            revision="local_general",
        ),
        assumptions=[],
        warnings=[],
        critic_status="revision_recommended",
        revision_performed=True,
        used_safe_fallback=False,
        trace=trace,
    )

    assert prompt_plan.strategy == plan.strategy
    assert draft.role is ModelRole.WORKER
    assert quality.status is CriticStatus.REVISION_RECOMMENDED
    assert (
        json.loads(final.model_dump_json())["trace"]["events"][0]["stage"] == "critic"
    )


def test_unknown_enum_value_fails_clearly() -> None:
    data = example_execution_plan_data()
    data["strategy"] = "keyword_classifier"

    with pytest.raises(ValidationError, match="strategy"):
        ExecutionPlan.model_validate(data)


def test_clarification_consistency_rules_are_enforced() -> None:
    with pytest.raises(ValidationError, match="question"):
        ClarificationDecision(
            action="ask_clarification",
            question=None,
            reason="The requested source text is missing.",
        )

    with pytest.raises(ValidationError, match="question"):
        ClarificationDecision(
            action="proceed",
            question="What scale do you expect?",
            reason="Enough information exists to proceed.",
        )


def test_critic_consistency_rules_are_enforced() -> None:
    with pytest.raises(ValidationError, match="revision_recommended"):
        CriticResult(
            schema_version=1,
            passes=True,
            issues=[],
            violated_criteria=[],
            revision_recommended=True,
            revision_instruction="Revise anyway.",
            concise_summary="Conflicting result.",
        )

    with pytest.raises(ValidationError, match="major or critical"):
        CriticResult(
            schema_version=1,
            passes=True,
            issues=[
                CriticIssue(
                    code="missing_constraint",
                    severity=CriticIssueSeverity.MAJOR,
                    message="Missing a required criterion.",
                    criterion="State assumptions",
                )
            ],
            violated_criteria=[],
            revision_recommended=False,
            revision_instruction=None,
            concise_summary="Conflicting result.",
        )

    with pytest.raises(ValidationError, match="revision_instruction"):
        CriticResult(
            schema_version=1,
            passes=False,
            issues=[],
            violated_criteria=[],
            revision_recommended=True,
            revision_instruction=None,
            concise_summary="Needs revision.",
        )


def test_final_response_consistency_rules_are_enforced() -> None:
    roles = RoleModelNames(
        understanding="local_general",
        worker="local_general",
        critic="local_general",
        revision="local_general",
    )

    with pytest.raises(ValidationError, match="clarification_question"):
        FinalResponse(
            status=PipelineStatus.CLARIFICATION_REQUIRED,
            text="",
            clarification_question=None,
            roles=roles,
            critic_status="skipped",
            revision_performed=False,
            used_safe_fallback=False,
        )


def test_secret_bearing_values_are_not_domain_fields() -> None:
    domain_models = [
        PromptRequest,
        TaskUnderstanding,
        ClarificationDecision,
        ExecutionPlan,
        ModelRequest,
        ModelResponse,
        DraftResponse,
        CriticResult,
        FinalResponse,
        TraceEvent,
    ]

    field_names = {
        field_name for model in domain_models for field_name in model.model_fields
    }

    assert "api_key" not in field_names
    assert "api_key_env" not in field_names
    assert "authorization" not in field_names
