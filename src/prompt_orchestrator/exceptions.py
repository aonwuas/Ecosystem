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


class InputError(PromptOrchestratorError):
    """Caller input is invalid."""

    code = "INPUT_ERROR"


class ProviderError(PromptOrchestratorError):
    """A model provider request failed."""

    code = "PROVIDER_ERROR"


class ProviderTimeoutError(ProviderError):
    """A model provider request timed out."""

    code = "PROVIDER_TIMEOUT"


class ProviderAuthenticationError(ProviderError):
    """A model provider rejected authentication."""

    code = "PROVIDER_AUTHENTICATION"


class StructuredOutputError(PromptOrchestratorError):
    """Structured model output could not be extracted or validated."""

    code = "STRUCTURED_OUTPUT_ERROR"


class ExecutionPlanValidationError(PromptOrchestratorError):
    """A model-produced execution plan failed deterministic validation."""

    code = "EXECUTION_PLAN_VALIDATION_ERROR"


class PolicyError(PromptOrchestratorError):
    """A model-produced plan violates deterministic execution policy."""

    code = "POLICY_ERROR"


class WorkerError(PromptOrchestratorError):
    """Worker prompt planning or generation failed."""

    code = "WORKER_ERROR"


class CriticError(PromptOrchestratorError):
    """Critic review failed."""

    code = "CRITIC_ERROR"


class RevisionError(PromptOrchestratorError):
    """Revision generation failed."""

    code = "REVISION_ERROR"


class PromptRenderError(PromptOrchestratorError):
    """A package-controlled prompt template could not be rendered."""

    code = "PROMPT_RENDER_ERROR"
