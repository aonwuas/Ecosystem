"""Aggregated model-call cost accounting models.

These models make the cost of a pipeline run explicit so orchestration quality
can be weighed against its token and latency premium. They are provider-neutral
and populated by the metering client wrapper, not by the stages themselves.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import Field

from prompt_orchestrator.domain._base import DomainModel, ShortText
from prompt_orchestrator.domain.enums import ModelRole

MAX_CALL_RECORDS = 64


class CallRecord(DomainModel):
    """One recorded model call and its measured cost."""

    role: ModelRole
    request_kind: ShortText
    model_name: ShortText
    input_tokens: int | None = Field(default=None, ge=0, strict=True)
    output_tokens: int | None = Field(default=None, ge=0, strict=True)
    total_tokens: int | None = Field(default=None, ge=0, strict=True)
    duration_ms: float = Field(default=0.0, ge=0.0)
    is_repair: bool = Field(default=False, strict=True)


class RunUsage(DomainModel):
    """Aggregated cost accounting across every model call in one operation."""

    call_count: int = Field(default=0, ge=0, strict=True)
    input_tokens: int | None = Field(default=None, ge=0, strict=True)
    output_tokens: int | None = Field(default=None, ge=0, strict=True)
    total_tokens: int | None = Field(default=None, ge=0, strict=True)
    total_duration_ms: float = Field(default=0.0, ge=0.0)
    calls: list[CallRecord] = Field(default_factory=list, max_length=MAX_CALL_RECORDS)

    @classmethod
    def from_calls(cls, calls: list[CallRecord]) -> RunUsage:
        """Aggregate a list of call records into a run-level summary.

        Token totals stay ``None`` unless at least one call reported that field,
        so callers can distinguish "provider reported zero" from "not reported".
        """
        return cls(
            call_count=len(calls),
            input_tokens=_sum_optional(record.input_tokens for record in calls),
            output_tokens=_sum_optional(record.output_tokens for record in calls),
            total_tokens=_sum_optional(record.total_tokens for record in calls),
            total_duration_ms=sum(record.duration_ms for record in calls),
            calls=list(calls),
        )


def _sum_optional(values: Iterable[int | None]) -> int | None:
    total: int | None = None
    for value in values:
        if value is None:
            continue
        total = value if total is None else total + value
    return total
