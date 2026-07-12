"""Final response construction independent of CLI rendering."""

from __future__ import annotations

from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import (
    DraftResponse,
    FinalResponse,
    QualityResult,
    RoleModelNames,
    Trace,
    ValidatedExecutionPlan,
)
from prompt_orchestrator.domain.enums import (
    ClarificationAction,
    CriticStatus,
    PipelineStatus,
)


def finalize_completed(
    *,
    draft: DraftResponse,
    validated_plan: ValidatedExecutionPlan,
    quality: QualityResult,
    revision_performed: bool,
    warnings: list[str],
    config: PromptOrchestratorConfig,
    trace: Trace | None = None,
) -> FinalResponse:
    """Build a completed final response after worker and quality stages."""
    all_warnings = [
        *validated_plan.validation_warnings,
        *quality.warnings,
        *warnings,
        *draft.warnings,
    ]
    status = (
        PipelineStatus.COMPLETED_WITH_WARNINGS
        if all_warnings or quality.status is CriticStatus.NOT_CHECKED
        else PipelineStatus.COMPLETED
    )
    return FinalResponse(
        status=status,
        text=draft.text,
        clarification_question=None,
        strategy=validated_plan.plan.strategy,
        roles=_roles(config),
        assumptions=validated_plan.plan.understanding.assumptions,
        warnings=_dedupe(all_warnings),
        critic_status=quality.status,
        revision_performed=revision_performed,
        used_safe_fallback=validated_plan.used_safe_fallback,
        trace=trace,
    )


def finalize_plan_gate(
    *,
    validated_plan: ValidatedExecutionPlan,
    config: PromptOrchestratorConfig,
    trace: Trace | None = None,
) -> FinalResponse | None:
    """Return a final response for clarification/refusal gate outcomes."""
    clarification = validated_plan.plan.clarification
    if clarification.action is ClarificationAction.ASK_CLARIFICATION:
        return FinalResponse(
            status=PipelineStatus.CLARIFICATION_REQUIRED,
            text="",
            clarification_question=clarification.question,
            strategy=validated_plan.plan.strategy,
            roles=_roles(config),
            assumptions=validated_plan.plan.understanding.assumptions,
            warnings=validated_plan.validation_warnings,
            critic_status=CriticStatus.SKIPPED,
            revision_performed=False,
            used_safe_fallback=validated_plan.used_safe_fallback,
            trace=trace,
        )
    if clarification.action is ClarificationAction.REFUSE_OR_REDIRECT:
        return FinalResponse(
            status=PipelineStatus.REFUSED,
            text=clarification.reason,
            clarification_question=None,
            strategy=validated_plan.plan.strategy,
            roles=_roles(config),
            assumptions=validated_plan.plan.understanding.assumptions,
            warnings=validated_plan.validation_warnings,
            critic_status=CriticStatus.SKIPPED,
            revision_performed=False,
            used_safe_fallback=validated_plan.used_safe_fallback,
            trace=trace,
        )
    return None


def finalize_failed(
    *,
    error: Exception,
    config: PromptOrchestratorConfig,
    trace: Trace | None = None,
) -> FinalResponse:
    """Build a failed final response for controlled application failures."""
    code = getattr(error, "code", "PIPELINE_FAILED")
    return FinalResponse(
        status=PipelineStatus.FAILED,
        text=f"Error [{code}]: {error}",
        clarification_question=None,
        strategy=None,
        roles=_roles(config),
        assumptions=[],
        warnings=[],
        critic_status=CriticStatus.FAILED,
        revision_performed=False,
        used_safe_fallback=False,
        trace=trace,
    )


def _roles(config: PromptOrchestratorConfig) -> RoleModelNames:
    return RoleModelNames(
        understanding=config.roles.understanding,
        worker=config.roles.worker,
        critic=config.roles.critic,
        revision=config.roles.revision,
    )


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
