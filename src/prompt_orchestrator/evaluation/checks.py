"""Deterministic, model-free checks on a produced answer.

These checks are the backbone of the evaluation: they run without any model and
give a stable pass/fail signal per case and per arm (orchestrated vs baseline),
so regressions are visible even when no judge model is available.
"""

from __future__ import annotations

from pydantic import Field

from prompt_orchestrator.domain import FinalResponse
from prompt_orchestrator.domain._base import DomainModel, ShortText
from prompt_orchestrator.domain.enums import PipelineStatus
from prompt_orchestrator.evaluation.corpus import EvalChecks


class CheckOutcome(DomainModel):
    """Result of applying deterministic checks to one answer."""

    passed: bool = Field(strict=True)
    checked: int = Field(ge=0, strict=True)
    failures: list[ShortText] = Field(default_factory=list, max_length=50)


def evaluate_checks(response: FinalResponse, checks: EvalChecks) -> CheckOutcome:
    """Apply the case's deterministic expectations to a final response."""
    failures: list[str] = []
    checked = 0

    answer = _answer_text(response)
    haystack = answer.casefold()

    for needle in checks.must_include:
        checked += 1
        if needle.casefold() not in haystack:
            failures.append(f"missing required text: {needle!r}")

    for needle in checks.must_avoid:
        checked += 1
        if needle.casefold() in haystack:
            failures.append(f"contains prohibited text: {needle!r}")

    if checks.min_length is not None:
        checked += 1
        if len(answer) < checks.min_length:
            failures.append(
                f"answer shorter than min_length {checks.min_length} "
                f"(was {len(answer)})"
            )

    if checks.max_length is not None:
        checked += 1
        if len(answer) > checks.max_length:
            failures.append(
                f"answer longer than max_length {checks.max_length} (was {len(answer)})"
            )

    if checks.expect_status is not None:
        checked += 1
        if response.status is not checks.expect_status:
            failures.append(
                f"expected status {checks.expect_status.value}, "
                f"got {response.status.value}"
            )

    return CheckOutcome(
        passed=not failures,
        checked=checked,
        failures=[_truncate(failure) for failure in failures],
    )


def _answer_text(response: FinalResponse) -> str:
    if response.status is PipelineStatus.CLARIFICATION_REQUIRED:
        return response.clarification_question or ""
    return response.text


def _truncate(value: str) -> str:
    return value if len(value) <= 500 else f"{value[:497]}..."
