"""Critic plus optional one-pass revision coordination."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_orchestrator.clients import ModelClient
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import DraftResponse, IntakeResult, QualityResult
from prompt_orchestrator.domain.enums import CriticStatus
from prompt_orchestrator.domain.execution_plan import ValidatedExecutionPlan
from prompt_orchestrator.stages.critic import run_critic_stage
from prompt_orchestrator.stages.revision import run_revision_stage


@dataclass(frozen=True)
class QualityStageResult:
    """Quality-stage output after critic and optional one-pass revision."""

    draft: DraftResponse
    quality: QualityResult
    revision_performed: bool
    warnings: list[str]


def run_quality_stage(
    *,
    intake: IntakeResult,
    validated_plan: ValidatedExecutionPlan,
    draft: DraftResponse,
    config: PromptOrchestratorConfig,
    client: ModelClient,
) -> QualityStageResult:
    """Run critic review and at most one revision."""
    critic_stage = run_critic_stage(
        intake=intake,
        validated_plan=validated_plan,
        draft=draft,
        config=config,
        client=client,
    )
    warnings = list(critic_stage.quality.warnings)
    if (
        critic_stage.quality.status is CriticStatus.REVISION_RECOMMENDED
        and critic_stage.critic_result is not None
    ):
        revision = run_revision_stage(
            intake=intake,
            validated_plan=validated_plan,
            draft=draft,
            critic_result=critic_stage.critic_result,
            config=config,
            client=client,
        )
        warnings.extend(revision.warnings)
        return QualityStageResult(
            draft=revision.draft,
            quality=QualityResult(
                status=critic_stage.quality.status,
                critic_result=critic_stage.critic_result,
                warnings=warnings,
            ),
            revision_performed=revision.revision_performed,
            warnings=warnings,
        )

    return QualityStageResult(
        draft=draft,
        quality=critic_stage.quality,
        revision_performed=False,
        warnings=warnings,
    )
