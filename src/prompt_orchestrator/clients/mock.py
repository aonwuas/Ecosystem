"""Deterministic model clients for tests and examples."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from types import TracebackType
from typing import Self

from prompt_orchestrator.domain import ModelRequest, ModelResponse, TokenUsage
from prompt_orchestrator.exceptions import ProviderError


class MockModelClient:
    """Return a fixed response and record provider-neutral requests."""

    def __init__(self, text: str = "Mock response") -> None:
        self.text = text
        self.requests: list[ModelRequest] = []
        self.close_count = 0
        self._closed = False

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(
            text=self.text,
            model=request.model_name,
            finish_reason="stop",
            usage=TokenUsage(),
            provider_metadata={"provider": "mock"},
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.close_count += 1

    async def aclose(self) -> None:
        self.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


@dataclass(frozen=True)
class ScriptedResponse:
    """One expected scripted client interaction."""

    expect: str
    text: str | None = None
    error: ProviderError | None = None
    model: str | None = None
    finish_reason: str = "stop"


class ScriptedModelClient:
    """Consume an ordered response script and verify request order."""

    def __init__(self, script: Iterable[ScriptedResponse | dict[str, object]]) -> None:
        self._script = [self._coerce_step(step) for step in script]
        self.requests: list[ModelRequest] = []
        self._index = 0
        self.close_count = 0
        self._closed = False

    @property
    def remaining(self) -> int:
        return len(self._script) - self._index

    def generate(self, request: ModelRequest) -> ModelResponse:
        if self._index >= len(self._script):
            raise AssertionError("scripted client received more calls than expected")

        step = self._script[self._index]
        self._index += 1
        self.requests.append(request)

        if request.request_kind != step.expect:
            raise AssertionError(
                f"expected request_kind '{step.expect}', got '{request.request_kind}'"
            )
        if step.error is not None:
            raise step.error
        if step.text is None:
            raise AssertionError("scripted response requires text when no error is set")

        return ModelResponse(
            text=step.text,
            model=step.model or request.model_name,
            finish_reason=step.finish_reason,
            usage=TokenUsage(),
            provider_metadata={"provider": "scripted"},
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.close_count += 1

    async def aclose(self) -> None:
        self.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    @staticmethod
    def _coerce_step(step: ScriptedResponse | dict[str, object]) -> ScriptedResponse:
        if isinstance(step, ScriptedResponse):
            return step
        error = step.get("error")
        if error is not None and not isinstance(error, ProviderError):
            raise TypeError("scripted error must be a ProviderError")
        expect = step.get("expect")
        if not isinstance(expect, str):
            raise TypeError("scripted step requires string 'expect'")
        text = step.get("text")
        if text is not None and not isinstance(text, str):
            raise TypeError("scripted step 'text' must be a string")
        model = step.get("model")
        if model is not None and not isinstance(model, str):
            raise TypeError("scripted step 'model' must be a string")
        finish_reason = step.get("finish_reason", "stop")
        if not isinstance(finish_reason, str):
            raise TypeError("scripted step 'finish_reason' must be a string")
        return ScriptedResponse(
            expect=expect,
            text=text,
            error=error,
            model=model,
            finish_reason=finish_reason,
        )
