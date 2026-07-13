"""Application-level pipeline runner independent of CLI presentation."""

from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Self

from prompt_orchestrator.clients import ModelClient
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import (
    FinalResponse,
    IntakeResult,
    PromptPlan,
    PromptRequest,
    Trace,
    TraceEvent,
    ValidatedExecutionPlan,
)
from prompt_orchestrator.domain.enums import CriticStatus
from prompt_orchestrator.exceptions import PromptOrchestratorError
from prompt_orchestrator.pipeline.state import PipelineState, PipelineStateMachine
from prompt_orchestrator.stages import (
    build_worker_prompt_plan,
    run_quality_stage,
    run_understanding_stage,
    run_worker_stage,
)
from prompt_orchestrator.stages.finalizer import (
    finalize_completed,
    finalize_failed,
    finalize_plan_gate,
)
from prompt_orchestrator.stages.trace import TraceCollector


@dataclass(frozen=True)
class PipelinePlanResult:
    """Result for the plan operation."""

    intake: IntakeResult | None
    validated_plan: ValidatedExecutionPlan | None
    prompt_plan: PromptPlan | None
    final_response: FinalResponse | None
    trace: Trace | None


@dataclass(frozen=True)
class PipelineRunResult:
    """Result for a full pipeline run operation."""

    final_response: FinalResponse
    state_history: tuple[PipelineState, ...]


class PipelineRunner:
    """Synchronous application service that connects orchestration stages."""

    def __init__(
        self,
        *,
        config: PromptOrchestratorConfig,
        client: ModelClient,
    ) -> None:
        self._config = config
        self._client = client

    def close(self) -> None:
        """Close the underlying model client."""
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def understand(
        self,
        request: PromptRequest,
    ) -> tuple[IntakeResult, ValidatedExecutionPlan]:
        """Run intake and understanding through deterministic policy validation."""
        result = run_understanding_stage(
            request,
            config=self._config,
            client=self._client,
        )
        return result.intake, result.validated_plan

    def plan(
        self,
        request: PromptRequest,
        *,
        include_trace: bool = False,
    ) -> PipelinePlanResult:
        """Return a worker prompt plan without calling the worker."""
        machine = PipelineStateMachine()
        trace = TraceCollector()
        try:
            understanding = run_understanding_stage(
                request,
                config=self._config,
                client=self._client,
            )
            machine.transition(PipelineState.INTAKE_COMPLETE)
            machine.transition(PipelineState.UNDERSTANDING_COMPLETE)
            machine.transition(PipelineState.PLAN_VALIDATED)
            trace.add_event(
                stage="pipeline",
                event="understood",
                status="ok",
                details={
                    "strategy": understanding.validated_plan.plan.strategy.value,
                    "understanding_fallback": (
                        understanding.validated_plan.used_safe_fallback
                    ),
                },
            )
            gate = finalize_plan_gate(
                validated_plan=understanding.validated_plan,
                config=self._config,
                trace=_optional_trace(
                    include_trace,
                    understanding.trace,
                    trace.to_trace(),
                ),
            )
            if gate is not None:
                if gate.clarification_question is not None:
                    machine.transition(PipelineState.CLARIFICATION_REQUIRED)
                else:
                    machine.transition(PipelineState.REFUSED)
                machine.transition(PipelineState.FINALIZED)
                return PipelinePlanResult(
                    intake=understanding.intake,
                    validated_plan=understanding.validated_plan,
                    prompt_plan=None,
                    final_response=gate,
                    trace=gate.trace,
                )

            prompt_plan = build_worker_prompt_plan(
                intake=understanding.intake,
                validated_plan=understanding.validated_plan,
            )
            trace.add_event(
                stage="worker",
                event="prompt_planned",
                status="ok",
                details={
                    "strategy": prompt_plan.strategy.value,
                    "worker_role": prompt_plan.worker_role.value,
                    "quality_criteria": len(prompt_plan.quality_criteria),
                },
            )
            return PipelinePlanResult(
                intake=understanding.intake,
                validated_plan=understanding.validated_plan,
                prompt_plan=prompt_plan,
                final_response=None,
                trace=_optional_trace(
                    include_trace,
                    understanding.trace,
                    trace.to_trace(),
                ),
            )
        except PromptOrchestratorError as error:
            machine.transition(PipelineState.FAILED)
            final = finalize_failed(
                error=error,
                config=self._config,
                trace=_optional_trace(include_trace, trace.to_trace()),
            )
            machine.transition(PipelineState.FINALIZED)
            return PipelinePlanResult(
                intake=_failed_intake_placeholder(request),
                validated_plan=None,
                prompt_plan=None,
                final_response=final,
                trace=final.trace,
            )

    def run(
        self,
        request: PromptRequest,
        *,
        include_trace: bool = False,
    ) -> PipelineRunResult:
        """Run understanding, worker generation, critic/revision, and finalization."""
        machine = PipelineStateMachine()
        trace = TraceCollector()
        understanding_trace: Trace | None = None
        try:
            understanding = run_understanding_stage(
                request,
                config=self._config,
                client=self._client,
            )
            understanding_trace = understanding.trace
            machine.transition(PipelineState.INTAKE_COMPLETE)
            machine.transition(PipelineState.UNDERSTANDING_COMPLETE)
            machine.transition(PipelineState.PLAN_VALIDATED)
            trace.add_event(
                stage="pipeline",
                event="plan_validated",
                status="ok",
                details={
                    "strategy": understanding.validated_plan.plan.strategy.value,
                    "policy_changes": len(understanding.validated_plan.policy_changes),
                },
            )

            gate = finalize_plan_gate(
                validated_plan=understanding.validated_plan,
                config=self._config,
                trace=_optional_trace(
                    include_trace,
                    understanding_trace,
                    trace.to_trace(),
                ),
            )
            if gate is not None:
                if gate.clarification_question is not None:
                    machine.transition(PipelineState.CLARIFICATION_REQUIRED)
                    trace.add_event(
                        stage="finalizer",
                        event="clarification_required",
                        status="ok",
                    )
                else:
                    machine.transition(PipelineState.REFUSED)
                    trace.add_event(stage="finalizer", event="refused", status="ok")
                final = gate.model_copy(
                    update={
                        "trace": _optional_trace(
                            include_trace,
                            understanding_trace,
                            trace.to_trace(),
                        )
                    }
                )
                machine.transition(PipelineState.FINALIZED)
                return PipelineRunResult(
                    final_response=final,
                    state_history=tuple(machine.history),
                )

            worker = run_worker_stage(
                intake=understanding.intake,
                validated_plan=understanding.validated_plan,
                config=self._config,
                client=self._client,
            )
            machine.transition(PipelineState.WORKER_COMPLETE)
            trace.add_event(
                stage="worker",
                event="generated",
                status="ok",
                details={
                    "model_name": worker.draft.model_name,
                    "text_length": len(worker.draft.text),
                },
            )
            quality = run_quality_stage(
                intake=understanding.intake,
                validated_plan=understanding.validated_plan,
                draft=worker.draft,
                config=self._config,
                client=self._client,
            )
            self._transition_quality(
                machine,
                quality.quality.status,
                quality.revision_performed,
                quality.warnings,
            )
            trace.add_event(
                stage="quality",
                event="reviewed",
                status="ok",
                details={
                    "critic_status": quality.quality.status.value,
                    "revision_performed": quality.revision_performed,
                    "warnings": len(quality.warnings),
                },
            )
            final = finalize_completed(
                draft=quality.draft,
                validated_plan=understanding.validated_plan,
                quality=quality.quality,
                revision_performed=quality.revision_performed,
                warnings=quality.warnings,
                config=self._config,
                trace=_optional_trace(
                    include_trace,
                    understanding_trace,
                    trace.to_trace(),
                ),
            )
            trace.add_event(
                stage="finalizer",
                event="completed",
                status="ok",
                details={"status": final.status.value},
            )
            final = final.model_copy(
                update={
                    "trace": _optional_trace(
                        include_trace,
                        understanding_trace,
                        trace.to_trace(),
                    )
                }
            )
            machine.transition(PipelineState.FINALIZED)
            return PipelineRunResult(
                final_response=final,
                state_history=tuple(machine.history),
            )
        except PromptOrchestratorError as error:
            machine.transition(PipelineState.FAILED)
            trace.add_event(
                stage="pipeline",
                event="failed",
                status="failed",
                error_code=error.code,
            )
            final = finalize_failed(
                error=error,
                config=self._config,
                trace=_optional_trace(
                    include_trace,
                    understanding_trace,
                    trace.to_trace(),
                ),
            )
            machine.transition(PipelineState.FINALIZED)
            return PipelineRunResult(
                final_response=final,
                state_history=tuple(machine.history),
            )

    @staticmethod
    def _transition_quality(
        machine: PipelineStateMachine,
        status: CriticStatus,
        revision_performed: bool,
        warnings: list[str],
    ) -> None:
        if status is CriticStatus.SKIPPED:
            machine.transition(PipelineState.CRITIC_SKIPPED)
            return
        if status is CriticStatus.NOT_CHECKED:
            machine.transition(PipelineState.CRITIC_FAILED)
            return
        machine.transition(PipelineState.CRITIC_COMPLETE)
        if revision_performed:
            machine.transition(PipelineState.REVISION_COMPLETE)
        elif any(warning.startswith("revision failed") for warning in warnings):
            machine.transition(PipelineState.REVISION_FAILED)
        elif any(warning.startswith("revision skipped") for warning in warnings):
            machine.transition(PipelineState.REVISION_SKIPPED)


def _optional_trace(include_trace: bool, *traces: Trace | None) -> Trace | None:
    if not include_trace:
        return None
    events: list[TraceEvent] = []
    for trace in traces:
        if trace is not None:
            events.extend(trace.events)
    return Trace(events=events)


def _failed_intake_placeholder(request: PromptRequest) -> IntakeResult:
    """Create a minimal intake shape only for failed plan results."""
    return IntakeResult(
        request=request,
        normalized_prompt=request.prompt,
        normalized_context=request.context,
        warnings=[],
    )
