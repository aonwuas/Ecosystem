"""Trace collectors for sanitized stage traces and explicit LLM I/O diagnostics."""

from __future__ import annotations

import json
from contextvars import ContextVar, Token
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from prompt_orchestrator.domain import ModelMessage, Trace, TraceEvent


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


@dataclass(frozen=True)
class LlmIoMessage:
    """One model request message captured for explicit diagnostics."""

    role: str
    content: str


@dataclass
class LlmIoCallRecord:
    """One explicit opt-in model I/O diagnostic record."""

    stage: str
    role: str
    model_name: str
    provider_name: str
    provider_type: str
    request_messages: list[LlmIoMessage]
    raw_response_text: str | None = None
    extracted_json: str | None = None
    validation_error: str | None = None
    provider_error: str | None = None

    def to_jsonable(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "role": self.role,
            "model_name": self.model_name,
            "provider_name": self.provider_name,
            "provider_type": self.provider_type,
            "request_messages": [
                {"role": message.role, "content": message.content}
                for message in self.request_messages
            ],
            "raw_response_text": self.raw_response_text,
            "extracted_json": self.extracted_json,
            "validation_error": self.validation_error,
            "provider_error": self.provider_error,
        }


class LlmIoTraceRecorder:
    """Collect explicit, unsanitized model prompts and responses on request."""

    def __init__(self) -> None:
        self.records: list[LlmIoCallRecord] = []
        self._active_index: int | None = None

    def start_call(
        self,
        *,
        stage: str,
        role: str,
        model_name: str,
        provider_name: str,
        provider_type: str,
        messages: list[ModelMessage],
    ) -> int:
        record = LlmIoCallRecord(
            stage=stage,
            role=role,
            model_name=model_name,
            provider_name=provider_name,
            provider_type=provider_type,
            request_messages=[
                LlmIoMessage(role=message.role, content=message.content)
                for message in messages
            ],
        )
        self.records.append(record)
        self._active_index = len(self.records) - 1
        return self._active_index

    def finish_call(self, index: int, raw_response_text: str) -> None:
        self.records[index].raw_response_text = raw_response_text
        self._active_index = index

    def finish_provider_error(self, index: int, error: Exception) -> None:
        self.records[index].provider_error = f"{type(error).__name__}: {error}"
        self._active_index = index

    def record_extracted_json(self, text: str) -> None:
        if self._active_index is not None:
            self.records[self._active_index].extracted_json = text

    def record_validation_error(self, error: str) -> None:
        if self._active_index is not None:
            self.records[self._active_index].validation_error = error

    def render_text(self) -> str:
        rendered: list[str] = []
        for record in self.records:
            rendered.extend(
                [
                    f"===== LLM CALL: {record.stage} =====",
                    f"Role: {record.role}",
                    f"Model: {record.model_name}",
                    f"Provider: {record.provider_name} ({record.provider_type})",
                    "",
                    "----- REQUEST MESSAGES -----",
                ]
            )
            for message in record.request_messages:
                rendered.extend([f"[{message.role}]", message.content, ""])
            rendered.extend(
                [
                    "----- RAW RESPONSE -----",
                    record.raw_response_text or "",
                ]
            )
            if record.extracted_json is not None:
                rendered.extend(
                    ["", "----- EXTRACTED JSON -----", record.extracted_json]
                )
            if record.validation_error is not None:
                rendered.extend(
                    ["", "----- VALIDATION ERROR -----", record.validation_error]
                )
            if record.provider_error is not None:
                rendered.extend(
                    ["", "----- PROVIDER ERROR -----", record.provider_error]
                )
            rendered.extend(["", f"===== END LLM CALL: {record.stage} =====", ""])
        return "\n".join(rendered).rstrip()

    def render_jsonl(self) -> str:
        return "\n".join(
            json.dumps(record.to_jsonable(), ensure_ascii=False)
            for record in self.records
        )


_CURRENT_LLM_IO_RECORDER: ContextVar[LlmIoTraceRecorder | None] = ContextVar(
    "prompt_orchestrator_llm_io_recorder",
    default=None,
)


def current_llm_io_recorder() -> LlmIoTraceRecorder | None:
    """Return the active explicit LLM I/O recorder, if one is enabled."""
    return _CURRENT_LLM_IO_RECORDER.get()


def set_current_llm_io_recorder(
    recorder: LlmIoTraceRecorder | None,
) -> Token[LlmIoTraceRecorder | None]:
    """Set the active explicit LLM I/O recorder for the current context."""
    return _CURRENT_LLM_IO_RECORDER.set(recorder)


def reset_current_llm_io_recorder(
    token: Token[LlmIoTraceRecorder | None],
) -> None:
    """Restore the previous explicit LLM I/O recorder."""
    _CURRENT_LLM_IO_RECORDER.reset(token)
