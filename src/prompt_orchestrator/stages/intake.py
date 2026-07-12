"""Prompt intake and normalization."""

from __future__ import annotations

from prompt_orchestrator.domain import IntakeResult, PromptRequest
from prompt_orchestrator.exceptions import InputError


def normalize_input(request: PromptRequest) -> IntakeResult:
    """Normalize caller input without interpreting intent."""
    normalized_prompt = _normalize_text(request.prompt)
    if normalized_prompt == "":
        raise InputError("Prompt must not be empty.", code="INPUT_EMPTY")

    normalized_context = (
        _normalize_text(request.context) if request.context is not None else None
    )
    if normalized_context == "":
        normalized_context = None

    normalized_request = PromptRequest(
        prompt=normalized_prompt,
        context=normalized_context,
        requested_output_mode=request.requested_output_mode,
        conversation_id=request.conversation_id,
        metadata=request.metadata,
    )
    return IntakeResult(
        request=normalized_request,
        normalized_prompt=normalized_prompt,
        normalized_context=normalized_context,
        warnings=[],
    )


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()
