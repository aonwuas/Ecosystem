"""Application exception types."""

from __future__ import annotations


class PromptOrchestratorError(Exception):
    """Base class for expected application errors."""

    code = "PROMPT_ORCHESTRATOR_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class ConfigurationError(PromptOrchestratorError):
    """Configuration loading, validation, or resolution failed."""

    code = "CONFIGURATION_ERROR"
