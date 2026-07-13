"""Metering model-client wrapper for run-level cost accounting.

This wrapper follows the same decorator pattern as ``DiagnosticModelClient``:
it delegates generation to an inner client while recording the role, request
kind, reported token usage, and measured latency of every call. Aggregating
those records into a :class:`RunUsage` makes the cost of a pipeline run explicit
so the quality benefit of orchestration can be weighed against its token and
latency premium.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from types import TracebackType
from typing import Self

from prompt_orchestrator.clients.base import ModelClient
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import (
    CallRecord,
    ModelRequest,
    ModelResponse,
    RunUsage,
)

_REPAIR_MARKER = "<INVALID_RESPONSE>"


class MeteringModelClient:
    """Record per-call token usage and latency while delegating generation."""

    def __init__(
        self,
        inner: ModelClient,
        *,
        config: PromptOrchestratorConfig,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._inner = inner
        self._config = config
        self._clock = clock
        self._records: list[CallRecord] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        resolved = self._config.resolve_role(request.role)
        started = self._clock()
        try:
            response = self._inner.generate(request)
        except Exception:
            # Failed calls still consumed time; record what we can so cost
            # accounting reflects wasted effort, then re-raise unchanged.
            self._records.append(
                CallRecord(
                    role=request.role,
                    request_kind=request.request_kind,
                    model_name=resolved.model_name,
                    duration_ms=self._elapsed_ms(started),
                    is_repair=_is_repair_request(request),
                )
            )
            raise
        self._records.append(
            CallRecord(
                role=request.role,
                request_kind=request.request_kind,
                model_name=resolved.model_name,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.total_tokens,
                duration_ms=self._elapsed_ms(started),
                is_repair=_is_repair_request(request),
            )
        )
        return response

    def snapshot(self) -> RunUsage:
        """Return the aggregated usage recorded since the last reset."""
        return RunUsage.from_calls(self._records)

    def reset(self) -> None:
        """Discard recorded calls so the next operation meters from zero."""
        self._records = []

    def _elapsed_ms(self, started: float) -> float:
        return max(0.0, (self._clock() - started) * 1000.0)

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


def _is_repair_request(request: ModelRequest) -> bool:
    return any(_REPAIR_MARKER in message.content for message in request.messages)
