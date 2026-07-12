"""Provider-neutral model request and response models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from prompt_orchestrator.domain._base import (
    BoundedText,
    DomainModel,
    JsonObject,
    OptionalBoundedText,
    ShortText,
)
from prompt_orchestrator.domain.enums import ModelRole


class ModelMessage(DomainModel):
    """One provider-neutral chat message."""

    role: Literal["system", "user", "assistant"]
    content: BoundedText


class ModelRequest(DomainModel):
    """Provider-neutral generation request."""

    role: ModelRole
    model_name: ShortText
    messages: list[ModelMessage] = Field(min_length=1, max_length=20)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0, strict=True)
    max_output_tokens: int = Field(default=4096, gt=0, le=131_072, strict=True)
    timeout_seconds: int = Field(default=180, gt=0, le=3600, strict=True)
    request_kind: ShortText


class TokenUsage(DomainModel):
    """Optional token accounting returned by a provider."""

    input_tokens: int | None = Field(default=None, ge=0, strict=True)
    output_tokens: int | None = Field(default=None, ge=0, strict=True)
    total_tokens: int | None = Field(default=None, ge=0, strict=True)


class ModelResponse(DomainModel):
    """Provider-neutral generation response."""

    text: OptionalBoundedText
    model: ShortText | None = None
    finish_reason: ShortText | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    provider_metadata: JsonObject = Field(default_factory=dict)
