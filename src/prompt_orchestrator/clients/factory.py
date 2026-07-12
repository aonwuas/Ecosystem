"""Model client factory for configured providers."""

from __future__ import annotations

from prompt_orchestrator.clients.base import ModelClient
from prompt_orchestrator.clients.mock import MockModelClient
from prompt_orchestrator.clients.openai_compatible import OpenAICompatibleModelClient
from prompt_orchestrator.config.models import (
    MockProviderConfig,
    OpenAICompatibleProviderConfig,
    PromptOrchestratorConfig,
)
from prompt_orchestrator.domain import ModelRole
from prompt_orchestrator.exceptions import ConfigurationError


class ClientFactory:
    """Create provider clients from validated configuration."""

    def __init__(self, config: PromptOrchestratorConfig) -> None:
        self._config = config

    def create_for_role(self, role: ModelRole) -> ModelClient:
        resolved = self._config.resolve_role(role)
        provider = resolved.provider
        if isinstance(provider, MockProviderConfig):
            return MockModelClient()
        if isinstance(provider, OpenAICompatibleProviderConfig):
            return OpenAICompatibleModelClient(
                provider,
                resolved.model,
                transient_retries=self._config.runtime.transient_http_retries,
            )
        raise ConfigurationError(
            f"Unsupported provider type for role '{role.value}'.",
            code="CONFIG_PROVIDER_UNSUPPORTED",
        )


def create_client_for_role(
    config: PromptOrchestratorConfig,
    role: ModelRole,
) -> ModelClient:
    """Create a model client for a configured logical role."""
    return ClientFactory(config).create_for_role(role)
