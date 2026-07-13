"""Tests for the metering model-client wrapper and cost accounting."""

from __future__ import annotations

from collections.abc import Callable

from prompt_orchestrator.clients import MeteringModelClient
from prompt_orchestrator.clients.mock import MockModelClient, ScriptedModelClient
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import (
    ModelMessage,
    ModelRequest,
    RunUsage,
    TokenUsage,
)
from prompt_orchestrator.domain.enums import ModelRole


def scripted_config() -> PromptOrchestratorConfig:
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


def _request(role: ModelRole, kind: str, *, content: str = "hello") -> ModelRequest:
    return ModelRequest(
        role=role,
        model_name="scripted_general",
        messages=[ModelMessage(role="user", content=content)],
        request_kind=kind,
    )


def _make_clock() -> Callable[[], float]:
    ticks = [0.0, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    state = {"i": 0}

    def clock() -> float:
        value = ticks[min(state["i"], len(ticks) - 1)]
        state["i"] += 1
        return value

    return clock


def test_metering_aggregates_tokens_and_calls() -> None:
    config: PromptOrchestratorConfig = scripted_config()
    inner = MockModelClient(
        "answer",
        usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
    )
    metering = MeteringModelClient(inner, config=config)

    metering.generate(_request(ModelRole.WORKER, "worker"))
    metering.generate(_request(ModelRole.CRITIC, "critic"))

    usage = metering.snapshot()
    assert isinstance(usage, RunUsage)
    assert usage.call_count == 2
    assert usage.input_tokens == 20
    assert usage.output_tokens == 10
    assert usage.total_tokens == 30
    assert [record.request_kind for record in usage.calls] == ["worker", "critic"]
    assert usage.calls[0].role is ModelRole.WORKER


def test_metering_reset_clears_records() -> None:
    config = scripted_config()
    metering = MeteringModelClient(MockModelClient("answer"), config=config)
    metering.generate(_request(ModelRole.WORKER, "worker"))
    metering.reset()
    usage = metering.snapshot()
    assert usage.call_count == 0
    assert usage.total_tokens is None


def test_metering_missing_usage_stays_none() -> None:
    config = scripted_config()
    metering = MeteringModelClient(MockModelClient("answer"), config=config)
    metering.generate(_request(ModelRole.WORKER, "worker"))
    usage = metering.snapshot()
    assert usage.call_count == 1
    assert usage.total_tokens is None
    assert usage.calls[0].total_tokens is None


def test_metering_records_duration_from_clock() -> None:
    config = scripted_config()
    clock = _make_clock()
    metering = MeteringModelClient(
        MockModelClient("answer"), config=config, clock=clock
    )
    metering.generate(_request(ModelRole.WORKER, "worker"))
    usage = metering.snapshot()
    # First call spans ticks 0.0 -> 0.5 seconds == 500 ms.
    assert usage.calls[0].duration_ms == 500.0
    assert usage.total_duration_ms == 500.0


def test_metering_flags_repair_requests() -> None:
    config = scripted_config()
    metering = MeteringModelClient(MockModelClient("answer"), config=config)
    metering.generate(
        _request(ModelRole.CRITIC, "critic", content="fix <INVALID_RESPONSE> now")
    )
    usage = metering.snapshot()
    assert usage.calls[0].is_repair is True


def test_metering_records_failed_calls_and_reraises() -> None:
    config = scripted_config()
    inner = ScriptedModelClient([])  # empty script raises on any call
    metering = MeteringModelClient(inner, config=config)
    raised = False
    try:
        metering.generate(_request(ModelRole.WORKER, "worker"))
    except AssertionError:
        raised = True
    assert raised
    usage = metering.snapshot()
    assert usage.call_count == 1
    assert usage.calls[0].total_tokens is None
