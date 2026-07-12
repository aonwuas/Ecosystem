"""Provider-neutral model client interface."""

from __future__ import annotations

from typing import Protocol

from prompt_orchestrator.domain import ModelRequest, ModelResponse


class ModelClient(Protocol):
    """Provider-neutral generation interface."""

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate text for a provider-neutral request."""
