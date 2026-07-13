"""Diagnostic model-client wrapper for explicit LLM I/O tracing."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from prompt_orchestrator.clients.base import ModelClient
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import ModelRequest, ModelResponse
from prompt_orchestrator.stages.trace import LlmIoTraceRecorder


class DiagnosticModelClient:
    """Record exact model requests and responses while delegating generation."""

    def __init__(
        self,
        inner: ModelClient,
        *,
        config: PromptOrchestratorConfig,
        recorder: LlmIoTraceRecorder,
    ) -> None:
        self._inner = inner
        self._config = config
        self._recorder = recorder

    def generate(self, request: ModelRequest) -> ModelResponse:
        resolved = self._config.resolve_role(request.role)
        provider = resolved.provider
        index = self._recorder.start_call(
            stage=_diagnostic_stage_name(request),
            role=request.role.value,
            model_name=resolved.model_name,
            provider_name=resolved.provider_name,
            provider_type=provider.type,
            messages=request.messages,
        )
        try:
            response = self._inner.generate(request)
        except Exception as exc:
            self._recorder.finish_provider_error(index, exc)
            raise
        self._recorder.finish_call(index, response.text)
        return response

    def close(self) -> None:
        self._inner.close()

    async def aclose(self) -> None:
        await self._inner.aclose()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def _diagnostic_stage_name(request: ModelRequest) -> str:
    if _is_repair_request(request):
        return f"{request.request_kind} repair"
    return request.request_kind


def _is_repair_request(request: ModelRequest) -> bool:
    return any("<INVALID_RESPONSE>" in message.content for message in request.messages)
