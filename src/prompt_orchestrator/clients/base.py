"""Provider-neutral model client interface."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from prompt_orchestrator.domain import ModelRequest, ModelResponse


class ModelClient(Protocol):
    """Provider-neutral generation interface."""

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate text for a provider-neutral request."""

    def close(self) -> None:
        """Release underlying resources. Implementations should be idempotent."""

    async def aclose(self) -> None:
        """Async-compatible close hook for future runtimes."""

    def __enter__(self) -> Self:
        """Enter a context manager for explicit lifecycle management."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit a context manager and close resources."""
