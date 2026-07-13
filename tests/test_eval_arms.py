"""Tests for the control-arm runners and the arm builder."""

from __future__ import annotations

import json

from prompt_orchestrator.clients import ScriptedModelClient
from prompt_orchestrator.clients.mock import ScriptedResponse
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import PromptRequest
from prompt_orchestrator.domain.enums import PipelineStatus
from prompt_orchestrator.evaluation.arms import ArmSpec, build_arms
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


def test_run_best_of_n_selects_reported_index() -> None:
    client = ScriptedModelClient(
        [
            ScriptedResponse(expect="candidate", text="Candidate zero."),
            ScriptedResponse(expect="candidate", text="Candidate one."),
            ScriptedResponse(
                expect="selection",
                text=json.dumps({"best_index": 1, "reason": "clearer"}),
            ),
        ]
    )
    runner = PipelineRunner(config=config(), client=client)
    response = runner.run_best_of_n(PromptRequest(prompt="Do it."), n=2)
    assert response.status is PipelineStatus.COMPLETED
    assert response.text == "Candidate one."
    assert client.remaining == 0


def test_run_best_of_n_out_of_range_index_falls_back() -> None:
    client = ScriptedModelClient(
        [
            ScriptedResponse(expect="candidate", text="Candidate zero."),
            ScriptedResponse(expect="candidate", text="Candidate one."),
            ScriptedResponse(
                expect="selection",
                text=json.dumps({"best_index": 9, "reason": "oops"}),
            ),
        ]
    )
    runner = PipelineRunner(config=config(), client=client)
    response = runner.run_best_of_n(PromptRequest(prompt="Do it."), n=2)
    # Out-of-range selection falls back to the first candidate.
    assert response.text == "Candidate zero."


def test_run_best_of_n_single_candidate_skips_selection() -> None:
    client = ScriptedModelClient(
        [ScriptedResponse(expect="candidate", text="Only candidate.")]
    )
    runner = PipelineRunner(config=config(), client=client)
    response = runner.run_best_of_n(PromptRequest(prompt="Do it."), n=1)
    assert response.text == "Only candidate."
    assert client.remaining == 0


def test_run_self_refine_uses_revision_when_present() -> None:
    client = ScriptedModelClient(
        [
            ScriptedResponse(expect="self_refine_draft", text="Rough draft."),
            ScriptedResponse(expect="self_refine_revise", text="Polished answer."),
        ]
    )
    runner = PipelineRunner(config=config(), client=client)
    response = runner.run_self_refine(PromptRequest(prompt="Do it."))
    assert response.text == "Polished answer."
    assert client.remaining == 0


def test_with_overrides_disables_critic() -> None:
    runner = PipelineRunner(config=config(), client=ScriptedModelClient([]))
    ablated = runner.with_overrides(enable_critic=False)
    assert ablated is not runner
    # The override is applied without mutating the original config.
    assert ablated._config.runtime.enable_critic is False
    assert runner._config.runtime.enable_critic is True


def test_build_arms_orders_treatment_first() -> None:
    runner = PipelineRunner(config=config(), client=ScriptedModelClient([]))
    arms = build_arms(
        runner,
        ArmSpec(controls=("single_call", "best_of_n"), best_of_n=3, ablations=True),
    )
    names = [arm.name for arm in arms]
    assert names[0] == "orchestrated"
    assert arms[0].is_treatment is True
    assert "single_call" in names
    assert "best_of_3" in names
    assert "ablation_no_critic" in names
    assert "ablation_no_revision" in names
