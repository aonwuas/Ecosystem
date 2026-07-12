"""OpenAI-compatible chat-completions model client."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from prompt_orchestrator.config.models import (
    ModelConfig,
    OpenAICompatibleProviderConfig,
)
from prompt_orchestrator.domain import ModelRequest, ModelResponse, TokenUsage
from prompt_orchestrator.exceptions import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderTimeoutError,
)

TRANSIENT_STATUS_CODES = {500, 502, 503, 504}


class OpenAICompatibleModelClient:
    """Generate text through an OpenAI-compatible chat-completions endpoint."""

    def __init__(
        self,
        provider: OpenAICompatibleProviderConfig,
        model: ModelConfig,
        *,
        transient_retries: int = 1,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._transient_retries = transient_retries
        self._client = http_client or httpx.Client(verify=provider.verify_tls)
        self._owns_client = http_client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def generate(self, request: ModelRequest) -> ModelResponse:
        payload = self._build_payload(request)
        headers = self._build_headers()
        url = f"{self._provider.base_url}/chat/completions"
        attempts = self._transient_retries + 1
        last_timeout: ProviderTimeoutError | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = self._client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=request.timeout_seconds,
                )
            except httpx.TimeoutException as exc:
                last_timeout = ProviderTimeoutError(
                    "Provider request timed out.",
                    code="PROVIDER_TIMEOUT",
                )
                if attempt < attempts:
                    continue
                raise last_timeout from exc
            except httpx.RequestError as exc:
                error = ProviderError(
                    "Provider request failed before a response was received.",
                    code="PROVIDER_REQUEST_FAILED",
                )
                if attempt < attempts:
                    continue
                raise error from exc

            if response.status_code in TRANSIENT_STATUS_CODES and attempt < attempts:
                continue
            return self._parse_response(response)

        if last_timeout is not None:
            raise last_timeout
        raise ProviderError("Provider request failed.", code="PROVIDER_REQUEST_FAILED")

    def _build_payload(self, request: ModelRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
        }
        payload.update(dict(self._model.extra_body))
        return payload

    def _build_headers(self) -> dict[str, str]:
        headers = dict(self._provider.default_headers)
        if self._provider.api_key is not None:
            headers["Authorization"] = f"Bearer {self._provider.api_key.reveal()}"
        return headers

    def _parse_response(self, response: httpx.Response) -> ModelResponse:
        if response.status_code in {401, 403}:
            raise ProviderAuthenticationError(
                f"Provider authentication failed with HTTP {response.status_code}.",
                code="PROVIDER_AUTHENTICATION",
            )
        if response.status_code >= 400:
            raise ProviderError(
                f"Provider request failed with HTTP {response.status_code}.",
                code="PROVIDER_HTTP_ERROR",
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError(
                "Provider returned invalid JSON.",
                code="PROVIDER_INVALID_RESPONSE",
            ) from exc

        text = _extract_text(data)
        usage_data = data.get("usage")
        usage = _parse_usage(usage_data if isinstance(usage_data, Mapping) else {})
        finish_reason = _extract_finish_reason(data)
        model = data.get("model")

        return ModelResponse(
            text=text,
            model=model if isinstance(model, str) else None,
            finish_reason=finish_reason,
            usage=usage,
            provider_metadata=_safe_metadata(data),
        )


def _extract_text(data: Mapping[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderError(
            "Provider response did not include choices.",
            code="PROVIDER_INVALID_RESPONSE",
        )
    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        raise ProviderError(
            "Provider response choice was invalid.",
            code="PROVIDER_INVALID_RESPONSE",
        )
    message = first_choice.get("message")
    if not isinstance(message, Mapping):
        raise ProviderError(
            "Provider response choice did not include a message.",
            code="PROVIDER_INVALID_RESPONSE",
        )
    content = message.get("content")
    if not isinstance(content, str):
        raise ProviderError(
            "Provider response message content was missing.",
            code="PROVIDER_INVALID_RESPONSE",
        )
    return content


def _extract_finish_reason(data: Mapping[str, Any]) -> str | None:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        return None
    finish_reason = first_choice.get("finish_reason")
    return finish_reason if isinstance(finish_reason, str) else None


def _parse_usage(data: Mapping[str, Any]) -> TokenUsage:
    input_tokens = _optional_int(data.get("prompt_tokens"))
    output_tokens = _optional_int(data.get("completion_tokens"))
    total_tokens = _optional_int(data.get("total_tokens"))
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _safe_metadata(data: Mapping[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    response_id = data.get("id")
    object_type = data.get("object")
    created = data.get("created")
    if isinstance(response_id, str):
        metadata["response_id"] = response_id
    if isinstance(object_type, str):
        metadata["object"] = object_type
    if isinstance(created, int):
        metadata["created"] = created
    return metadata
