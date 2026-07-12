"""Understanding and execution-plan domain models."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from prompt_orchestrator.domain._base import DomainModel, ShortText, StringList
from prompt_orchestrator.domain.enums import (
    AmbiguityLevel,
    ClarificationAction,
    ModelRole,
    OutputMode,
    RiskLevel,
    StrategyId,
    TaskComplexity,
)


class TaskUnderstanding(DomainModel):
    """Model-produced task analysis."""

    user_goal: ShortText
    intent: ShortText
    task_type: ShortText
    complexity: TaskComplexity
    ambiguity: AmbiguityLevel
    risk_level: RiskLevel
    risk_categories: StringList = Field(default_factory=list)
    missing_information: StringList = Field(default_factory=list)
    assumptions: StringList = Field(default_factory=list)
    uncertainties: StringList = Field(default_factory=list)
    concise_rationale: ShortText


class ClarificationDecision(DomainModel):
    """Decision to proceed, ask one question, or refuse/redirect."""

    action: ClarificationAction
    question: ShortText | None = None
    reason: ShortText

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        if (
            self.action is ClarificationAction.ASK_CLARIFICATION
            and self.question is None
        ):
            raise ValueError("ask_clarification requires one non-empty question")
        if self.action is ClarificationAction.PROCEED and self.question is not None:
            raise ValueError("proceed requires question to be null")
        if self.action is ClarificationAction.REFUSE_OR_REDIRECT and not self.reason:
            raise ValueError("refuse_or_redirect requires a user-facing reason")
        return self


class OutputContract(DomainModel):
    """Requested response shape and audience contract."""

    mode: OutputMode
    structure: ShortText
    tone: ShortText
    length: ShortText
    audience: ShortText


class ExecutionPlan(DomainModel):
    """Validated schema for model-produced orchestration control data."""

    schema_version: int = Field(1, strict=True)
    understanding: TaskUnderstanding
    clarification: ClarificationDecision
    strategy: StrategyId
    worker_role: ModelRole
    output_contract: OutputContract
    must_include: StringList = Field(default_factory=list)
    must_avoid: StringList = Field(default_factory=list)
    quality_criteria: StringList = Field(default_factory=list)
    critic_required: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_schema_version(self) -> Self:
        if self.schema_version != 1:
            raise ValueError("schema_version must equal 1")
        return self


class ValidatedExecutionPlan(DomainModel):
    """Application-owned wrapper around an accepted execution plan."""

    plan: ExecutionPlan
    policy_changes: StringList = Field(default_factory=list)
    validation_warnings: StringList = Field(default_factory=list)
    used_safe_fallback: bool = Field(default=False, strict=True)
