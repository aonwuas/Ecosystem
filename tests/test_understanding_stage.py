from __future__ import annotations

import json

import pytest

from prompt_orchestrator.clients import ScriptedModelClient
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import PromptRequest
from prompt_orchestrator.domain.enums import StrategyId
from prompt_orchestrator.exceptions import InputError
from prompt_orchestrator.stages import normalize_input, run_understanding_stage


def config_data(
    *,
    failure_mode: str = "clarify",
    repair_attempts: int = 1,
    default_output_mode: str = "text",
) -> dict[str, object]:
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
                "temperature": 0.1,
                "max_output_tokens": 3000,
                "timeout_seconds": 180,
            }
        },
        "roles": {
            "understanding": "scripted_general",
            "worker": "scripted_general",
            "critic": "scripted_general",
            "revision": "scripted_general",
        },
        "runtime": {
            "structured_output_repair_attempts": repair_attempts,
            "understanding_failure_mode": failure_mode,
            "default_output_mode": default_output_mode,
        },
    }


def config(
    *,
    failure_mode: str = "clarify",
    repair_attempts: int = 1,
    default_output_mode: str = "text",
) -> PromptOrchestratorConfig:
    return PromptOrchestratorConfig.model_validate(
        config_data(
            failure_mode=failure_mode,
            repair_attempts=repair_attempts,
            default_output_mode=default_output_mode,
        )
    )


def valid_plan_json(strategy: str = "comparison") -> str:
    return json.dumps(
        {
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
                "assumptions": [],
                "uncertainties": ["Scale is unspecified."],
                "concise_rationale": "The user is comparing technologies.",
            },
            "clarification": {
                "action": "proceed",
                "question": None,
                "reason": "A conditional comparison can be useful.",
            },
            "strategy": strategy,
            "output_contract": {
                "mode": "markdown",
                "structure": "comparison with recommendation",
                "tone": "practical and neutral",
                "length": "medium",
                "audience": "software developer",
            },
            "must_include": ["tradeoffs"],
            "must_avoid": ["pretending missing requirements are known"],
            "quality_criteria": ["State assumptions"],
            "critic_required": True,
        }
    )


def observed_bad_initial_output() -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "understanding": (
                "User requests assistance drafting a professional apology email."
            ),
            "clarification": None,
            "strategy": "draft_generation",
            "output_contract": "Markdown-formatted email draft.",
            "quality_criteria": "Tone must be respectful.",
            "rationale": "The user wants a polished written draft.",
            "assumptions": ["The apology should be professional."],
            "uncertainties": ["The specific recipient is unknown."],
        }
    )


def observed_bad_repair_output() -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "understanding": "User wants a professional apology email.",
            "clarification": {},
            "strategy": "draft_generation",
            "output_contract": {
                "format": "Markdown",
                "content": "Email draft",
            },
            "must_include": [],
            "must_avoid": [],
            "quality_criteria": ["Use respectful tone."],
            "critic_required": True,
        }
    )


def test_intake_normalizes_line_endings_and_context() -> None:
    request = PromptRequest(prompt="  hello\r\nworld  ", context="  context\rtext  ")

    intake = normalize_input(request)

    assert intake.normalized_prompt == "hello\nworld"
    assert intake.normalized_context == "context\ntext"
    assert intake.request.prompt == "hello\nworld"


def test_intake_rejects_empty_constructed_prompt() -> None:
    request = PromptRequest.model_construct(
        prompt="   ",
        context=None,
        requested_output_mode=None,
        conversation_id=None,
        metadata={},
    )

    with pytest.raises(InputError, match="empty"):
        normalize_input(request)


def test_understanding_stage_returns_valid_execution_plan() -> None:
    client = ScriptedModelClient(
        [{"expect": "understanding", "text": valid_plan_json()}]
    )

    result = run_understanding_stage(
        PromptRequest(prompt="Help me choose between SQLite and PostgreSQL"),
        config=config(),
        client=client,
    )

    assert result.validated_plan.plan.strategy is StrategyId.COMPARISON
    assert result.validated_plan.used_safe_fallback is False
    assert client.requests[0].role == "understanding"
    assert client.requests[0].model_name == "scripted_general"
    assert client.requests[0].temperature == 0.1
    assert client.requests[0].request_kind == "understanding"
    assert "Help me choose" in client.requests[0].messages[1].content
    assert "<USER_REQUEST>" in client.requests[0].messages[1].content
    assert '"understanding": {' in client.requests[0].messages[1].content
    assert '"output_contract": {' in client.requests[0].messages[1].content
    assert '"worker_role"' not in client.requests[0].messages[1].content
    assert "understanding must be an object" in client.requests[0].messages[1].content
    assert (
        "do not answer the user's task"
        in client.requests[0].messages[1].content.lower()
    )
    assert [event.stage for event in result.trace.events].count("understanding") >= 2


def test_invalid_first_output_is_repaired_once() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "understanding", "text": '{"schema_version": 1}'},
            {"expect": "understanding", "text": valid_plan_json("direct_answer")},
        ]
    )

    result = run_understanding_stage(
        PromptRequest(prompt="Answer this directly"),
        config=config(),
        client=client,
    )

    assert result.validated_plan.plan.strategy is StrategyId.DIRECT_ANSWER
    assert len(client.requests) == 2
    repair_prompt = client.requests[1].messages[1].content
    assert "<INVALID_RESPONSE>" in repair_prompt
    assert '{"schema_version": 1}' in repair_prompt
    assert any(event.event == "repair_validated" for event in result.trace.events)


def test_repair_prompt_addresses_observed_bad_shapes() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "understanding", "text": observed_bad_initial_output()},
            {"expect": "understanding", "text": observed_bad_repair_output()},
        ]
    )

    result = run_understanding_stage(
        PromptRequest(prompt="Help me write a professional apology email."),
        config=config(),
        client=client,
    )

    assert len(client.requests) == 2
    repair_prompt = client.requests[1].messages[1].content
    assert '"understanding": {' in repair_prompt
    assert '"clarification": {' in repair_prompt
    assert '"output_contract": {' in repair_prompt
    assert "understanding must be an object" in repair_prompt
    assert "clarification must include action and reason" in repair_prompt
    assert (
        "output_contract must use mode, structure, tone, length, and audience"
        in repair_prompt
    )
    assert "output_contract may not use format or content fields" in repair_prompt
    assert "Top-level rationale, assumptions, and uncertainties are not allowed" in (
        repair_prompt
    )
    assert result.validated_plan.plan.clarification.action == "ask_clarification"
    assert result.validated_plan.validation_warnings


def test_invalid_repair_requires_clarification_by_default() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "understanding", "text": '{"schema_version": 1}'},
            {"expect": "understanding", "text": '{"still": "bad"}'},
        ]
    )

    result = run_understanding_stage(
        PromptRequest(prompt="Please plan this"),
        config=config(),
        client=client,
    )

    assert len(client.requests) == 2
    assert result.validated_plan.plan.clarification.action == "ask_clarification"
    assert "couldn't confidently interpret" in (
        result.validated_plan.plan.clarification.question or ""
    )
    assert result.validated_plan.plan.understanding.risk_level == "high"


def test_understanding_failure_does_not_claim_prompt_was_understood() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "understanding", "text": '{"schema_version": 1}'},
            {"expect": "understanding", "text": '{"still": "bad"}'},
        ]
    )

    result = run_understanding_stage(
        PromptRequest(prompt="Give me a useful answer"),
        config=config(),
        client=client,
    )

    assert result.validated_plan.used_safe_fallback is True
    assert result.validated_plan.plan.strategy is StrategyId.STRUCTURED_ANALYSIS
    assert result.validated_plan.plan.clarification.action == "ask_clarification"
    assert any(event.event == "clarification_required" for event in result.trace.events)


def test_json_request_does_not_bypass_safe_understanding_failure() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "understanding", "text": '{"bad": true}'},
            {"expect": "understanding", "text": '{"still": "bad"}'},
        ]
    )

    result = run_understanding_stage(
        PromptRequest(prompt="Return JSON", requested_output_mode="json"),
        config=config(),
        client=client,
    )

    assert result.validated_plan.plan.clarification.action == "ask_clarification"
    assert result.validated_plan.plan.output_contract.mode == "json"


def test_runtime_default_markdown_is_in_understanding_prompt() -> None:
    client = ScriptedModelClient(
        [{"expect": "understanding", "text": valid_plan_json()}]
    )

    run_understanding_stage(
        PromptRequest(prompt="Compare options"),
        config=config(default_output_mode="markdown"),
        client=client,
    )

    assert "Requested output mode:\nmarkdown" in client.requests[0].messages[1].content


def test_no_repair_budget_errors_after_first_invalid_output() -> None:
    client = ScriptedModelClient([{"expect": "understanding", "text": '{"bad": true}'}])

    result = run_understanding_stage(
        PromptRequest(prompt="Understand this"),
        config=config(repair_attempts=0),
        client=client,
    )

    assert len(client.requests) == 1
    assert result.validated_plan.plan.clarification.action == "ask_clarification"
