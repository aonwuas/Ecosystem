"""Model client abstractions and provider adapters."""

from prompt_orchestrator.clients.base import ModelClient
from prompt_orchestrator.clients.diagnostic import DiagnosticModelClient
from prompt_orchestrator.clients.factory import (
    ClientFactory,
    RoutedModelClient,
    create_client_for_role,
    create_pipeline_client,
)
from prompt_orchestrator.clients.metering import MeteringModelClient
from prompt_orchestrator.clients.mock import MockModelClient, ScriptedModelClient
from prompt_orchestrator.clients.openai_compatible import OpenAICompatibleModelClient

__all__ = [
    "ClientFactory",
    "DiagnosticModelClient",
    "MeteringModelClient",
    "MockModelClient",
    "ModelClient",
    "OpenAICompatibleModelClient",
    "RoutedModelClient",
    "ScriptedModelClient",
    "create_client_for_role",
    "create_pipeline_client",
]
