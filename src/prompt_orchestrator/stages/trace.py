"""Small in-memory trace collector for stage tests and later pipeline use."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from prompt_orchestrator.domain import Trace, TraceEvent


class TraceCollector:
    """Collect sanitized trace events for one run."""

    def __init__(self) -> None:
        self._started_at = perf_counter()
        self._events: list[TraceEvent] = []

    def add_event(
        self,
        *,
        stage: str,
        event: str,
        status: str,
        attempt: int = 1,
        details: dict[str, Any] | None = None,
        warning_code: str | None = None,
        error_code: str | None = None,
    ) -> None:
        elapsed_ms = (perf_counter() - self._started_at) * 1000
        self._events.append(
            TraceEvent(
                stage=stage,
                event=event,
                status=status,
                duration_ms=elapsed_ms,
                attempt=attempt,
                details=_sanitize_details(details or {}),
                warning_code=warning_code,
                error_code=error_code,
            )
        )

    def to_trace(self) -> Trace:
        return Trace(events=list(self._events))


def _sanitize_details(details: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in details.items():
        lowered = key.lower()
        if "secret" in lowered or "api_key" in lowered or "authorization" in lowered:
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, str | int | float | bool) or value is None:
            sanitized[key] = value
        elif isinstance(value, list):
            sanitized[key] = [
                item
                if isinstance(item, str | int | float | bool) or item is None
                else str(item)
                for item in value
            ]
        else:
            sanitized[key] = str(value)
    return sanitized
