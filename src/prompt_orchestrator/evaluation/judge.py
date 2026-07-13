"""Opt-in pairwise model judge for treatment-vs-control comparison.

The judge is the only part of evaluation that needs a capable model, so it is
opt-in. To reduce position bias it judges each pair in **both orders** (treatment
as A then as B) and only declares a winner when both orders agree; a disagreement
is reported as a tie with ``order_consistent=False``. The judge currently reuses
the critic role model; using a distinct, stronger judge model is a later step.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from prompt_orchestrator.clients import ModelClient
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import FinalResponse, ModelMessage, ModelRequest
from prompt_orchestrator.domain._base import DomainModel, ShortText
from prompt_orchestrator.domain.enums import ModelRole, PipelineStatus
from prompt_orchestrator.evaluation.corpus import EvalCase
from prompt_orchestrator.exceptions import ProviderError, StructuredOutputError
from prompt_orchestrator.parsing import validate_structured_output
from prompt_orchestrator.prompts import load_template, render_template

JUDGE_VARIABLES = frozenset({"task", "answer_a", "answer_b", "rubric"})

JudgeWinner = Literal["treatment", "control", "tie"]


class JudgeResponse(DomainModel):
    """Raw structured judge output over slots A and B."""

    winner: Literal["a", "b", "tie"]
    confidence: int = Field(ge=1, le=5, strict=True)
    reason: ShortText


class JudgeVerdict(DomainModel):
    """Judge outcome for one pair, mapped to treatment vs control."""

    winner: JudgeWinner
    confidence: int = Field(ge=1, le=5, strict=True)
    reason: ShortText
    order_consistent: bool = Field(strict=True)


def judge_pair(
    *,
    case: EvalCase,
    treatment: FinalResponse,
    control: FinalResponse,
    config: PromptOrchestratorConfig,
    client: ModelClient,
) -> JudgeVerdict:
    """Judge treatment vs control in both orders and combine the verdicts."""
    # Order 1: treatment is slot A. Order 2: treatment is slot B.
    order1 = _judge_once(
        case=case,
        answer_a=_answer_text(treatment),
        answer_b=_answer_text(control),
        config=config,
        client=client,
    )
    order2 = _judge_once(
        case=case,
        answer_a=_answer_text(control),
        answer_b=_answer_text(treatment),
        config=config,
        client=client,
    )
    winner1 = _winner_from_slot(order1.winner, treatment_slot="a")
    winner2 = _winner_from_slot(order2.winner, treatment_slot="b")
    confidence = round((order1.confidence + order2.confidence) / 2)

    if winner1 == winner2:
        return JudgeVerdict(
            winner=winner1,
            confidence=confidence,
            reason=order1.reason,
            order_consistent=True,
        )
    return JudgeVerdict(
        winner="tie",
        confidence=confidence,
        reason=f"order-dependent: {order1.reason}",
        order_consistent=False,
    )


def _judge_once(
    *,
    case: EvalCase,
    answer_a: str,
    answer_b: str,
    config: PromptOrchestratorConfig,
    client: ModelClient,
) -> JudgeResponse:
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
    return validate_structured_output(response.text, JudgeResponse).value


# Errors the caller may choose to treat as a skipped judgement rather than fatal.
JudgeError = (ProviderError, StructuredOutputError)


def _winner_from_slot(
    slot_winner: Literal["a", "b", "tie"],
    *,
    treatment_slot: Literal["a", "b"],
) -> JudgeWinner:
    if slot_winner == "tie":
        return "tie"
    if slot_winner == treatment_slot:
        return "treatment"
    return "control"


def _answer_text(response: FinalResponse) -> str:
    if response.status is PipelineStatus.CLARIFICATION_REQUIRED:
        return response.clarification_question or ""
    return response.text
