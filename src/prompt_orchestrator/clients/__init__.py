"""Model client abstractions and provider adapters."""

from prompt_orchestrator.clients.base import ModelClient
from prompt_orchestrator.clients.factory import ClientFactory, create_client_for_role
from prompt_orchestrator.clients.mock import MockModelClient, ScriptedModelClient
from prompt_orchestrator.clients.openai_compatible import OpenAICompatibleModelClient

__all__ = [
    "ClientFactory",
    "MockModelClient",
    "ModelClient",
    "OpenAICompatibleModelClient",
    "ScriptedModelClient",
    "create_client_for_role",
]
