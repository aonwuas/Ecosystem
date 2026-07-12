"""Trace domain models."""

from __future__ import annotations

from pydantic import Field

from prompt_orchestrator.domain._base import DomainModel, JsonObject, ShortText


class TraceEvent(DomainModel):
    """One sanitized trace event for a single run."""

    stage: ShortText
    event: ShortText
    status: ShortText
    duration_ms: float = Field(ge=0.0, strict=True)
    attempt: int = Field(ge=1, strict=True)
    details: JsonObject = Field(default_factory=dict)
    warning_code: ShortText | None = None
    error_code: ShortText | None = None


class Trace(DomainModel):
    """Ordered in-memory trace data."""

    events: list[TraceEvent] = Field(default_factory=list, max_length=200)
