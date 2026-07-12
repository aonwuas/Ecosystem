"""Model client factory for configured providers."""

from __future__ import annotations

import json
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from prompt_orchestrator.clients.base import ModelClient
from prompt_orchestrator.clients.mock import MockModelClient, ScriptedModelClient
from prompt_orchestrator.clients.openai_compatible import OpenAICompatibleModelClient
from prompt_orchestrator.config.models import (
    MockProviderConfig,
    OpenAICompatibleProviderConfig,
    PromptOrchestratorConfig,
)
from prompt_orchestrator.domain import ModelRequest, ModelResponse, ModelRole
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


class RoutedModelClient:
    """Delegate each request to the client for its configured role."""

    def __init__(self, clients: dict[ModelRole, ModelClient]) -> None:
        self._clients = clients

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Generate with the role-specific client."""
        return self._clients[request.role].generate(request)


def create_pipeline_client(config: PromptOrchestratorConfig) -> ModelClient:
    """Create a client suitable for multi-role pipeline execution."""
    scripted = _shared_scripted_client(config)
    if scripted is not None:
        return scripted
    factory = ClientFactory(config)
    return RoutedModelClient(
        {role: factory.create_for_role(role) for role in ModelRole}
    )


def _shared_scripted_client(
    config: PromptOrchestratorConfig,
) -> ScriptedModelClient | None:
    mock_providers = [
        provider
        for provider in config.providers.values()
        if isinstance(provider, MockProviderConfig)
    ]
    if len(mock_providers) != 1:
        return None
    mock_provider_name = next(
        name
        for name, provider in config.providers.items()
        if isinstance(provider, MockProviderConfig)
    )
    if any(model.provider != mock_provider_name for model in config.models.values()):
        return None
    fixture_path = Path(mock_providers[0].fixture_path)
    if not fixture_path.is_file():
        return None
    try:
        raw = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigurationError(
            f"Could not read scripted mock fixture '{fixture_path}'.",
            code="CONFIG_FIXTURE_READ_FAILED",
        ) from exc
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ConfigurationError(
            "Scripted mock fixture must be a list of response steps.",
            code="CONFIG_FIXTURE_INVALID",
        )
    return ScriptedModelClient([_normalize_script_step(step) for step in raw])


def _normalize_script_step(step: object) -> dict[str, object]:
    if not isinstance(step, dict):
        raise ConfigurationError(
            "Scripted mock fixture steps must be mappings.",
            code="CONFIG_FIXTURE_INVALID",
        )
    normalized = dict(step)
    if "text" not in normalized:
        if "respond_text" in normalized:
            normalized["text"] = normalized["respond_text"]
        elif "respond_json" in normalized:
            normalized["text"] = json.dumps(normalized["respond_json"])
    return normalized
