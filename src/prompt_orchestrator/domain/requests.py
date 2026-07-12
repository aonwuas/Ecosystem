"""Request and intake domain models."""

from __future__ import annotations

from pydantic import Field

from prompt_orchestrator.domain._base import (
    DomainModel,
    JsonObject,
    OptionalBoundedText,
    StringList,
)
from prompt_orchestrator.domain.enums import OutputMode


class PromptRequest(DomainModel):
    """Caller input before model understanding."""

    prompt: OptionalBoundedText = Field(min_length=1)
    context: OptionalBoundedText | None = None
    requested_output_mode: OutputMode | None = None
    conversation_id: OptionalBoundedText | None = Field(default=None, max_length=200)
    metadata: JsonObject = Field(default_factory=dict)


class IntakeResult(DomainModel):
    """Normalized prompt input retained before understanding."""

    request: PromptRequest
    normalized_prompt: OptionalBoundedText = Field(min_length=1)
    normalized_context: OptionalBoundedText | None = None
    warnings: StringList = Field(default_factory=list)
