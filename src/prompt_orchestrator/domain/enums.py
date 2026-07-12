"""Canonical enumerations for domain schemas."""

from __future__ import annotations

from enum import StrEnum


class TaskComplexity(StrEnum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    MULTI_STEP = "multi_step"
    HIGH_STAKES = "high_stakes"


class AmbiguityLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ClarificationAction(StrEnum):
    PROCEED = "proceed"
    ASK_CLARIFICATION = "ask_clarification"
    REFUSE_OR_REDIRECT = "refuse_or_redirect"


class PipelineStatus(StrEnum):
    COMPLETED = "completed"
    CLARIFICATION_REQUIRED = "clarification_required"
    REFUSED = "refused"
    FAILED = "failed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"


class CriticStatus(StrEnum):
    PASSED = "passed"
    REVISION_RECOMMENDED = "revision_recommended"
    FAILED = "failed"
    NOT_CHECKED = "not_checked"
    SKIPPED = "skipped"


class OutputMode(StrEnum):
    TEXT = "text"
    MARKDOWN = "markdown"
    JSON = "json"


class StrategyId(StrEnum):
    DIRECT_ANSWER = "direct_answer"
    CONCISE_EXPLANATION = "concise_explanation"
    STEP_BY_STEP_EXPLANATION = "step_by_step_explanation"
    STRUCTURED_ANALYSIS = "structured_analysis"
    PLANNING = "planning"
    COMPARISON = "comparison"
    DECISION_SUPPORT = "decision_support"
    BRAINSTORMING = "brainstorming"
    DRAFT_GENERATION = "draft_generation"
    REWRITE_PRESERVE_MEANING = "rewrite_preserve_meaning"
    SUMMARIZATION = "summarization"
    INFORMATION_EXTRACTION = "information_extraction"
    STRUCTURED_OUTPUT = "structured_output"
    CREATIVE_GENERATION = "creative_generation"
    EMPATHETIC_GUIDANCE = "empathetic_guidance"
    TECHNICAL_ASSISTANCE = "technical_assistance"
    SAFETY_REDIRECT = "safety_redirect"


class ModelRole(StrEnum):
    UNDERSTANDING = "understanding"
    WORKER = "worker"
    CRITIC = "critic"
    REVISION = "revision"


class CriticIssueSeverity(StrEnum):
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"
