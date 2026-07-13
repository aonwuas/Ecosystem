"""Draft, critic, quality, prompt-plan, and final-response models."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from prompt_orchestrator.domain._base import (
    BoundedText,
    DomainModel,
    ShortText,
    StringList,
)
from prompt_orchestrator.domain.enums import (
    CriticIssueSeverity,
    CriticStatus,
    ModelRole,
    PipelineStatus,
    StrategyId,
)
from prompt_orchestrator.domain.execution_plan import OutputContract
from prompt_orchestrator.domain.model_io import TokenUsage
from prompt_orchestrator.domain.trace import Trace
from prompt_orchestrator.domain.usage import RunUsage


class PromptPlan(DomainModel):
    """Rendered worker prompt plan for planning and worker execution."""

    strategy: StrategyId
    worker_role: ModelRole
    system_prompt: BoundedText
    user_prompt: BoundedText
    output_contract: OutputContract
    quality_criteria: StringList = Field(default_factory=list)


class DraftResponse(DomainModel):
    """Worker draft answer with model metadata."""

    text: BoundedText
    model_name: ShortText
    role: ModelRole
    warnings: StringList = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)


class CriticIssue(DomainModel):
    """One bounded critic finding."""

    code: ShortText
    severity: CriticIssueSeverity
    message: ShortText
    criterion: ShortText | None = None


class CriticResult(DomainModel):
    """Structured critic review."""

    schema_version: int = Field(1, strict=True)
    passes: bool = Field(strict=True)
    issues: list[CriticIssue] = Field(default_factory=list, max_length=20)
    violated_criteria: StringList = Field(default_factory=list)
    revision_recommended: bool = Field(strict=True)
    revision_instruction: ShortText | None = None
    concise_summary: ShortText

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        if self.schema_version != 1:
            raise ValueError("schema_version must equal 1")
        has_major_or_critical_issue = any(
            issue.severity in {CriticIssueSeverity.MAJOR, CriticIssueSeverity.CRITICAL}
            for issue in self.issues
        )
        if self.passes and self.revision_recommended:
            raise ValueError("passes=true requires revision_recommended=false")
        if self.passes and has_major_or_critical_issue:
            raise ValueError("passes=true forbids major or critical issues")
        if self.revision_recommended and self.revision_instruction is None:
            raise ValueError("revision_recommended requires a revision_instruction")
        return self


class QualityResult(DomainModel):
    """Application-owned critic outcome."""

    status: CriticStatus
    critic_result: CriticResult | None = None
    warnings: StringList = Field(default_factory=list)


class RoleModelNames(DomainModel):
    """Resolved model names used for each MVP role."""

    understanding: ShortText
    worker: ShortText
    critic: ShortText
    revision: ShortText


class FinalResponse(DomainModel):
    """Final user-visible result plus sanitized orchestration metadata."""

    status: PipelineStatus
    text: str = Field(default="", strict=True, max_length=20_000)
    clarification_question: ShortText | None = None
    strategy: StrategyId | None = None
    roles: RoleModelNames
    assumptions: StringList = Field(default_factory=list)
    warnings: StringList = Field(default_factory=list)
    critic_status: CriticStatus
    revision_performed: bool = Field(strict=True)
    used_safe_fallback: bool = Field(strict=True)
    trace: Trace | None = None
    usage: RunUsage | None = None

    @model_validator(mode="after")
    def validate_final_shape(self) -> Self:
        if self.status is PipelineStatus.CLARIFICATION_REQUIRED:
            if self.clarification_question is None:
                raise ValueError(
                    "clarification_required requires clarification_question"
                )
            return self
        if self.status is PipelineStatus.REFUSED and not self.text.strip():
            raise ValueError("refused requires user-facing text")
        if (
            self.status
            in {
                PipelineStatus.COMPLETED,
                PipelineStatus.COMPLETED_WITH_WARNINGS,
            }
            and not self.text.strip()
        ):
            raise ValueError("completed responses require non-empty text")
        return self
