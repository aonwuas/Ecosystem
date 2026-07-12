"""Explicit pipeline state machine."""

from __future__ import annotations

from enum import StrEnum

from prompt_orchestrator.exceptions import PipelineStateError


class PipelineState(StrEnum):
    """Pipeline states allowed by the MVP architecture."""

    NEW = "new"
    INTAKE_COMPLETE = "intake_complete"
    UNDERSTANDING_COMPLETE = "understanding_complete"
    PLAN_VALIDATED = "plan_validated"
    CLARIFICATION_REQUIRED = "clarification_required"
    REFUSED = "refused"
    WORKER_COMPLETE = "worker_complete"
    CRITIC_COMPLETE = "critic_complete"
    CRITIC_SKIPPED = "critic_skipped"
    CRITIC_FAILED = "critic_failed"
    REVISION_COMPLETE = "revision_complete"
    REVISION_SKIPPED = "revision_skipped"
    REVISION_FAILED = "revision_failed"
    FINALIZED = "finalized"
    FAILED = "failed"


_ALLOWED_TRANSITIONS: dict[PipelineState, frozenset[PipelineState]] = {
    PipelineState.NEW: frozenset({PipelineState.INTAKE_COMPLETE, PipelineState.FAILED}),
    PipelineState.INTAKE_COMPLETE: frozenset(
        {PipelineState.UNDERSTANDING_COMPLETE, PipelineState.FAILED}
    ),
    PipelineState.UNDERSTANDING_COMPLETE: frozenset(
        {PipelineState.PLAN_VALIDATED, PipelineState.FAILED}
    ),
    PipelineState.PLAN_VALIDATED: frozenset(
        {
            PipelineState.CLARIFICATION_REQUIRED,
            PipelineState.REFUSED,
            PipelineState.WORKER_COMPLETE,
            PipelineState.FAILED,
        }
    ),
    PipelineState.CLARIFICATION_REQUIRED: frozenset({PipelineState.FINALIZED}),
    PipelineState.REFUSED: frozenset({PipelineState.FINALIZED}),
    PipelineState.WORKER_COMPLETE: frozenset(
        {
            PipelineState.CRITIC_COMPLETE,
            PipelineState.CRITIC_SKIPPED,
            PipelineState.CRITIC_FAILED,
            PipelineState.FAILED,
        }
    ),
    PipelineState.CRITIC_COMPLETE: frozenset(
        {
            PipelineState.REVISION_COMPLETE,
            PipelineState.REVISION_SKIPPED,
            PipelineState.REVISION_FAILED,
            PipelineState.FINALIZED,
            PipelineState.FAILED,
        }
    ),
    PipelineState.CRITIC_SKIPPED: frozenset({PipelineState.FINALIZED}),
    PipelineState.CRITIC_FAILED: frozenset(
        {PipelineState.FINALIZED, PipelineState.FAILED}
    ),
    PipelineState.REVISION_COMPLETE: frozenset({PipelineState.FINALIZED}),
    PipelineState.REVISION_SKIPPED: frozenset({PipelineState.FINALIZED}),
    PipelineState.REVISION_FAILED: frozenset({PipelineState.FINALIZED}),
    PipelineState.FAILED: frozenset({PipelineState.FINALIZED}),
    PipelineState.FINALIZED: frozenset(),
}


class PipelineStateMachine:
    """Validate legal pipeline state transitions."""

    def __init__(self) -> None:
        self.state = PipelineState.NEW
        self.history: list[PipelineState] = [self.state]

    def transition(self, next_state: PipelineState) -> None:
        """Move to an allowed state or fail clearly."""
        if next_state not in _ALLOWED_TRANSITIONS[self.state]:
            raise PipelineStateError(
                "Illegal pipeline transition "
                f"{self.state.value} -> {next_state.value}.",
                code="PIPELINE_STATE_ILLEGAL_TRANSITION",
            )
        self.state = next_state
        self.history.append(next_state)
