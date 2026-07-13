from __future__ import annotations

import json

import pytest

from prompt_orchestrator.clients import ScriptedModelClient
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import PromptRequest
from prompt_orchestrator.domain.enums import (
    CriticStatus,
    PipelineStatus,
    StrategyId,
)
from prompt_orchestrator.exceptions import PipelineStateError
from prompt_orchestrator.pipeline import (
    PipelineRunner,
    PipelineState,
    PipelineStateMachine,
)


def config(*, strict_critic: bool = False) -> PromptOrchestratorConfig:
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
                    "temperature": 0.1,
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
            },
        }
    )


def plan_json(
    *,
    strategy: str = "comparison",
    action: str = "proceed",
    question: str | None = None,
) -> str:
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
                "assumptions": ["The application is early-stage."],
                "uncertainties": ["Expected concurrency is unknown."],
                "concise_rationale": "The user is comparing database options.",
            },
            "clarification": {
                "action": action,
                "question": question,
                "reason": "A conditional answer is useful."
                if action == "proceed"
                else "A required detail is missing.",
            },
            "strategy": strategy,
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
    )


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


def request() -> PromptRequest:
    return PromptRequest(
        prompt="Help me choose between SQLite and PostgreSQL.",
        context="The app starts small.",
    )


def test_pipeline_run_completed_with_critic_pass() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "understanding", "text": plan_json()},
            {"expect": "worker", "text": "Draft answer."},
            {"expect": "critic", "text": critic_pass_json()},
        ]
    )

    result = PipelineRunner(config=config(), client=client).run(request())

    assert result.final_response.status is PipelineStatus.COMPLETED
    assert result.final_response.text == "Draft answer."
    assert result.final_response.critic_status is CriticStatus.PASSED
    assert result.final_response.revision_performed is False
    assert result.final_response.trace is None
    assert result.state_history[-1] is PipelineState.FINALIZED
    assert [call.request_kind for call in client.requests] == [
        "understanding",
        "worker",
        "critic",
    ]


def test_pipeline_run_revision_recommendation_uses_revised_draft_once() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "understanding", "text": plan_json()},
            {"expect": "worker", "text": "Draft answer."},
            {"expect": "critic", "text": critic_revision_json()},
            {"expect": "revision", "text": "Revised answer."},
        ]
    )

    result = PipelineRunner(config=config(), client=client).run(request())

    assert result.final_response.text == "Revised answer."
    assert result.final_response.revision_performed is True
    assert result.final_response.critic_status is CriticStatus.REVISION_RECOMMENDED
    assert result.state_history.count(PipelineState.REVISION_COMPLETE) == 1
    assert [call.request_kind for call in client.requests].count("revision") == 1


def test_pipeline_run_revision_failure_preserves_original_with_warning() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "understanding", "text": plan_json()},
            {"expect": "worker", "text": "Draft answer."},
            {"expect": "critic", "text": critic_revision_json()},
            {"expect": "revision", "text": "   "},
        ]
    )

    result = PipelineRunner(config=config(), client=client).run(request())

    assert result.final_response.status is PipelineStatus.COMPLETED_WITH_WARNINGS
    assert result.final_response.text == "Draft answer."
    assert result.final_response.revision_performed is False
    assert any(
        "original draft preserved" in item for item in result.final_response.warnings
    )
    assert PipelineState.REVISION_FAILED in result.state_history


def test_pipeline_run_critic_failure_degrades_when_non_strict() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "understanding", "text": plan_json()},
            {"expect": "worker", "text": "Draft answer."},
            {"expect": "critic", "text": '{"bad": true}'},
            {"expect": "critic", "text": '{"still": "bad"}'},
        ]
    )

    result = PipelineRunner(config=config(), client=client).run(request())

    assert result.final_response.status is PipelineStatus.COMPLETED_WITH_WARNINGS
    assert result.final_response.critic_status is CriticStatus.NOT_CHECKED
    assert result.final_response.text == "Draft answer."
    assert PipelineState.CRITIC_FAILED in result.state_history


def test_pipeline_run_critic_failure_returns_failed_when_strict() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "understanding", "text": plan_json()},
            {"expect": "worker", "text": "Draft answer."},
            {"expect": "critic", "text": '{"bad": true}'},
            {"expect": "critic", "text": '{"still": "bad"}'},
        ]
    )

    result = PipelineRunner(config=config(strict_critic=True), client=client).run(
        request()
    )

    assert result.final_response.status is PipelineStatus.FAILED
    assert result.final_response.critic_status is CriticStatus.FAILED
    assert "CRITIC_FAILED" in result.final_response.text
    assert PipelineState.FAILED in result.state_history


def test_pipeline_run_clarification_stops_before_worker() -> None:
    client = ScriptedModelClient(
        [
            {
                "expect": "understanding",
                "text": plan_json(
                    action="ask_clarification",
                    question="What workload do you expect?",
                ),
            }
        ]
    )

    result = PipelineRunner(config=config(), client=client).run(request())

    assert result.final_response.status is PipelineStatus.CLARIFICATION_REQUIRED
    assert (
        result.final_response.clarification_question == "What workload do you expect?"
    )
    assert len(client.requests) == 1
    assert PipelineState.CLARIFICATION_REQUIRED in result.state_history


def test_understanding_failure_stops_before_worker_critic_or_revision() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "understanding", "text": '{"bad": true}'},
            {"expect": "understanding", "text": '{"still": "bad"}'},
        ]
    )

    result = PipelineRunner(config=config(), client=client).run(request())

    assert result.final_response.status is PipelineStatus.CLARIFICATION_REQUIRED
    assert "couldn't confidently interpret" in (
        result.final_response.clarification_question or ""
    )
    assert result.final_response.text == ""
    assert result.final_response.critic_status is CriticStatus.SKIPPED
    assert result.final_response.revision_performed is False
    assert [call.request_kind for call in client.requests] == [
        "understanding",
        "understanding",
    ]
    assert PipelineState.WORKER_COMPLETE not in result.state_history
    assert PipelineState.CRITIC_COMPLETE not in result.state_history
    assert PipelineState.REVISION_COMPLETE not in result.state_history


def test_json_request_understanding_failure_still_requires_clarification() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "understanding", "text": '{"bad": true}'},
            {"expect": "understanding", "text": '{"still": "bad"}'},
        ]
    )

    result = PipelineRunner(config=config(), client=client).run(
        PromptRequest(prompt="Return JSON", requested_output_mode="json")
    )

    assert result.final_response.status is PipelineStatus.CLARIFICATION_REQUIRED
    assert [call.request_kind for call in client.requests] == [
        "understanding",
        "understanding",
    ]


def test_pipeline_run_refusal_stops_before_worker() -> None:
    client = ScriptedModelClient(
        [
            {
                "expect": "understanding",
                "text": plan_json(
                    strategy="safety_redirect",
                    action="refuse_or_redirect",
                ),
            }
        ]
    )

    result = PipelineRunner(config=config(), client=client).run(request())

    assert result.final_response.status is PipelineStatus.REFUSED
    assert result.final_response.text == "A required detail is missing."
    assert len(client.requests) == 1
    assert PipelineState.REFUSED in result.state_history


def test_plan_operation_returns_prompt_plan_without_worker_call() -> None:
    client = ScriptedModelClient([{"expect": "understanding", "text": plan_json()}])

    result = PipelineRunner(config=config(), client=client).plan(request())

    assert result.prompt_plan is not None
    assert result.prompt_plan.strategy is StrategyId.COMPARISON
    assert result.final_response is None
    assert [call.request_kind for call in client.requests] == ["understanding"]


def test_trace_is_optional_and_sanitized() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "understanding", "text": plan_json()},
            {"expect": "worker", "text": "Draft answer."},
            {"expect": "critic", "text": critic_pass_json()},
        ]
    )

    result = PipelineRunner(config=config(), client=client).run(
        request(),
        include_trace=True,
    )

    assert result.final_response.trace is not None
    trace_text = result.final_response.trace.model_dump_json()
    assert "OPENAI_API_KEY" not in trace_text
    assert "Help me choose between SQLite" not in trace_text
    assert any(
        event.stage == "worker" and event.event == "generated"
        for event in result.final_response.trace.events
    )


def test_illegal_state_transition_fails() -> None:
    machine = PipelineStateMachine()

    with pytest.raises(PipelineStateError, match="Illegal pipeline transition"):
        machine.transition(PipelineState.WORKER_COMPLETE)
