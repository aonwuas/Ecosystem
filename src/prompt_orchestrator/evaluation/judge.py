"""Opt-in pairwise model judge for orchestrated-vs-baseline comparison.

The judge is the only part of evaluation that needs a capable model, so it is
opt-in. It performs a pairwise comparison and, to reduce position bias, the two
answers are assigned to slots A and B deterministically by case index; the raw
slot winner is then mapped back to "orchestrated" or "baseline".
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from prompt_orchestrator.clients import ModelClient
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import (
    FinalResponse,
    ModelMessage,
    ModelRequest,
)
from prompt_orchestrator.domain._base import DomainModel, ShortText
from prompt_orchestrator.domain.enums import ModelRole, PipelineStatus
from prompt_orchestrator.evaluation.corpus import EvalCase
from prompt_orchestrator.exceptions import ProviderError, StructuredOutputError
from prompt_orchestrator.parsing import validate_structured_output
from prompt_orchestrator.prompts import load_template, render_template

JUDGE_VARIABLES = frozenset({"task", "answer_a", "answer_b", "rubric"})

JudgeWinner = Literal["orchestrated", "baseline", "tie"]


class JudgeResponse(DomainModel):
    """Raw structured judge output over slots A and B."""

    winner: Literal["a", "b", "tie"]
    confidence: int = Field(ge=1, le=5, strict=True)
    reason: ShortText


class JudgeVerdict(DomainModel):
    """Judge outcome mapped back to orchestrated vs baseline."""

    winner: JudgeWinner
    confidence: int = Field(ge=1, le=5, strict=True)
    reason: ShortText
    orchestrated_slot: Literal["a", "b"]


def judge_pair(
    *,
    case: EvalCase,
    case_index: int,
    orchestrated: FinalResponse,
    baseline: FinalResponse,
    config: PromptOrchestratorConfig,
    client: ModelClient,
) -> JudgeVerdict:
    """Judge orchestrated vs baseline for one case using the critic role model."""
    orchestrated_slot: Literal["a", "b"] = "a" if case_index % 2 == 0 else "b"
    if orchestrated_slot == "a":
        answer_a, answer_b = _answer_text(orchestrated), _answer_text(baseline)
    else:
        answer_a, answer_b = _answer_text(baseline), _answer_text(orchestrated)

    prompt = render_template(
        load_template("judge.md"),
        {
            "task": case.prompt,
            "rubric": case.rubric or "none",
            "answer_a": answer_a,
            "answer_b": answer_b,
        },
        allowed_variables=JUDGE_VARIABLES,
    )
    resolved = config.resolve_role(ModelRole.CRITIC)
    response = client.generate(
        ModelRequest(
            role=ModelRole.CRITIC,
            model_name=resolved.model_name,
            messages=[
                ModelMessage(
                    role="system",
                    content=(
                        "You are Prompt Orchestrator's evaluation judge. "
                        "Return structured JSON only."
                    ),
                ),
                ModelMessage(role="user", content=prompt),
            ],
            temperature=resolved.model.temperature,
            max_output_tokens=resolved.model.max_output_tokens,
            timeout_seconds=resolved.model.timeout_seconds,
            request_kind="judge",
        )
    )
    parsed = validate_structured_output(response.text, JudgeResponse).value
    return JudgeVerdict(
        winner=_map_winner(parsed.winner, orchestrated_slot),
        confidence=parsed.confidence,
        reason=parsed.reason,
        orchestrated_slot=orchestrated_slot,
    )


# Errors the caller may choose to treat as a skipped judgement rather than fatal.
JudgeError = (ProviderError, StructuredOutputError)


def _map_winner(
    slot_winner: Literal["a", "b", "tie"],
    orchestrated_slot: Literal["a", "b"],
) -> JudgeWinner:
    if slot_winner == "tie":
        return "tie"
    if slot_winner == orchestrated_slot:
        return "orchestrated"
    return "baseline"


def _answer_text(response: FinalResponse) -> str:
    if response.status is PipelineStatus.CLARIFICATION_REQUIRED:
        return response.clarification_question or ""
    return response.text
