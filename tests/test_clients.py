from __future__ import annotations

import json

import httpx
import pytest

from prompt_orchestrator.clients import (
    ClientFactory,
    MockModelClient,
    OpenAICompatibleModelClient,
    RoutedModelClient,
    ScriptedModelClient,
)
from prompt_orchestrator.config.models import (
    ModelConfig,
    OpenAICompatibleProviderConfig,
    PromptOrchestratorConfig,
)
from prompt_orchestrator.domain import ModelMessage, ModelRequest, ModelResponse
from prompt_orchestrator.domain.enums import ModelRole
from prompt_orchestrator.exceptions import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderTimeoutError,
)


def model_request(kind: str = "worker") -> ModelRequest:
    return ModelRequest(
        role="worker",
        model_name="local_general",
        messages=[
            ModelMessage(role="system", content="System instructions"),
            ModelMessage(role="user", content="User prompt"),
        ],
        temperature=0.3,
        max_output_tokens=123,
        timeout_seconds=9,
        request_kind=kind,
    )


def ok_response(text: str = "Hello") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 123,
            "model": "server-model",
            "choices": [
                {
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        },
    )


def openai_client(
    handler: httpx.MockTransport,
    *,
    provider: OpenAICompatibleProviderConfig | None = None,
    model: ModelConfig | None = None,
    retries: int = 1,
) -> OpenAICompatibleModelClient:
    return OpenAICompatibleModelClient(
        provider
        or OpenAICompatibleProviderConfig(
            type="openai_compatible",
            base_url="http://127.0.0.1:8080/v1",
            api_key_env=None,
        ),
        model
        or ModelConfig(
            provider="local",
            model="configured-model",
            extra_body={"top_p": 0.9},
        ),
        transient_retries=retries,
        http_client=httpx.Client(transport=handler),
    )


def test_mock_client_records_requests_and_returns_response() -> None:
    client = MockModelClient(text="Fixed")
    request = model_request()

    response = client.generate(request)

    assert response.text == "Fixed"
    assert response.model == "local_general"
    assert client.requests == [request]


def test_scripted_client_verifies_call_order() -> None:
    client = ScriptedModelClient(
        [
            {"expect": "understanding", "text": "{}"},
            {"expect": "worker", "text": "Draft"},
        ]
    )

    first = client.generate(model_request("understanding"))
    second = client.generate(model_request("worker"))

    assert first.text == "{}"
    assert second.text == "Draft"
    assert client.remaining == 0


def test_scripted_client_fails_on_unexpected_call_order() -> None:
    client = ScriptedModelClient([{"expect": "critic", "text": "{}"}])

    with pytest.raises(AssertionError, match="expected request_kind"):
        client.generate(model_request("worker"))


def test_openai_compatible_payload_mapping_and_response_parsing() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return ok_response("Mapped response")

    client = openai_client(httpx.MockTransport(handler))

    response = client.generate(model_request())

    assert response == ModelResponse(
        text="Mapped response",
        model="server-model",
        finish_reason="stop",
        usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        provider_metadata={
            "response_id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 123,
        },
    )
    assert captured_request is not None
    assert captured_request.url == "http://127.0.0.1:8080/v1/chat/completions"
    payload = json.loads(captured_request.content)
    assert payload["model"] == "configured-model"
    assert payload["temperature"] == 0.3
    assert payload["max_tokens"] == 123
    assert payload["top_p"] == 0.9
    assert payload["messages"] == [
        {"role": "system", "content": "System instructions"},
        {"role": "user", "content": "User prompt"},
    ]


def test_openai_compatible_local_endpoint_may_omit_api_key() -> None:
    authorization_headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        authorization_headers.append(request.headers.get("authorization"))
        return ok_response()

    client = openai_client(httpx.MockTransport(handler))

    client.generate(model_request())

    assert authorization_headers == [None]


def test_openai_compatible_uses_api_key_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROMPT_ORCHESTRATOR_TEST_KEY", "secret-value")
    provider = OpenAICompatibleProviderConfig(
        type="openai_compatible",
        base_url="https://api.example.test/v1",
        api_key_env="PROMPT_ORCHESTRATOR_TEST_KEY",
    )
    authorization_headers: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        authorization_headers.append(request.headers.get("authorization"))
        return ok_response()

    client = openai_client(httpx.MockTransport(handler), provider=provider)

    client.generate(model_request())

    assert authorization_headers == ["Bearer secret-value"]


def test_openai_compatible_uses_secret_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROMPT_ORCHESTRATOR_HEADER_TOKEN", "header-secret")
    provider = OpenAICompatibleProviderConfig(
        type="openai_compatible",
        base_url="https://api.example.test/v1",
        default_headers={"X-Organization": "example-org"},
        secret_headers={"X-Private-Token": {"env": "PROMPT_ORCHESTRATOR_HEADER_TOKEN"}},
    )
    captured_headers: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.append(request.headers)
        return ok_response()

    client = openai_client(httpx.MockTransport(handler), provider=provider)

    client.generate(model_request())

    assert captured_headers[0]["x-organization"] == "example-org"
    assert captured_headers[0]["x-private-token"] == "header-secret"


def test_openai_compatible_transient_retry_is_bounded() -> None:
    statuses = [500, 200]
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        status = statuses.pop(0)
        if status == 500:
            return httpx.Response(500, json={"error": {"message": "temporary"}})
        return ok_response("Retried")

    client = openai_client(httpx.MockTransport(handler), retries=1)

    response = client.generate(model_request())

    assert response.text == "Retried"
    assert calls == 2


def test_openai_compatible_does_not_retry_authentication_failure() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"error": {"message": "bad secret"}})

    client = openai_client(httpx.MockTransport(handler), retries=1)

    with pytest.raises(ProviderAuthenticationError):
        client.generate(model_request())

    assert calls == 1


def test_openai_compatible_maps_timeout_after_retry() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.TimeoutException("timed out", request=request)

    client = openai_client(httpx.MockTransport(handler), retries=1)

    with pytest.raises(ProviderTimeoutError):
        client.generate(model_request())

    assert calls == 2


def test_openai_compatible_provider_errors_do_not_expose_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROMPT_ORCHESTRATOR_TEST_KEY", "secret-value")
    provider = OpenAICompatibleProviderConfig(
        type="openai_compatible",
        base_url="https://api.example.test/v1",
        api_key_env="PROMPT_ORCHESTRATOR_TEST_KEY",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={"error": {"message": "secret-value leaked from server"}},
        )

    client = openai_client(httpx.MockTransport(handler), provider=provider, retries=0)

    with pytest.raises(ProviderError) as error:
        client.generate(model_request())

    assert "secret-value" not in str(error.value)


def test_openai_compatible_invalid_response_is_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    client = openai_client(httpx.MockTransport(handler))

    with pytest.raises(ProviderError, match="choices"):
        client.generate(model_request())


def test_client_factory_creates_mock_and_openai_clients() -> None:
    mock_config = PromptOrchestratorConfig.model_validate(
        {
            "version": 1,
            "providers": {
                "scripted": {
                    "type": "mock",
                    "fixture_path": "tests/fixtures/scripted_models.yaml",
                }
            },
            "models": {
                "scripted_general": {
                    "provider": "scripted",
                    "model": "scripted-model",
                }
            },
            "roles": {
                "understanding": "scripted_general",
                "worker": "scripted_general",
                "critic": "scripted_general",
                "revision": "scripted_general",
            },
            "runtime": {},
        }
    )
    openai_config = PromptOrchestratorConfig.model_validate(
        {
            "version": 1,
            "providers": {
                "local": {
                    "type": "openai_compatible",
                    "base_url": "http://127.0.0.1:8080/v1",
                }
            },
            "models": {
                "local_general": {
                    "provider": "local",
                    "model": "local-model",
                }
            },
            "roles": {
                "understanding": "local_general",
                "worker": "local_general",
                "critic": "local_general",
                "revision": "local_general",
            },
            "runtime": {},
        }
    )

    assert isinstance(
        ClientFactory(mock_config).create_for_role(ModelRole.WORKER),
        MockModelClient,
    )
    assert isinstance(
        ClientFactory(openai_config).create_for_role(ModelRole.WORKER),
        OpenAICompatibleModelClient,
    )


def test_routed_client_close_is_idempotent_for_shared_clients() -> None:
    shared = MockModelClient()
    routed = RoutedModelClient(
        {
            ModelRole.UNDERSTANDING: shared,
            ModelRole.WORKER: shared,
            ModelRole.CRITIC: shared,
            ModelRole.REVISION: shared,
        }
    )

    routed.close()
    routed.close()

    assert shared.close_count == 1


def test_mock_and_scripted_clients_close_without_lifecycle_errors() -> None:
    mock = MockModelClient()
    scripted = ScriptedModelClient([{"expect": "worker", "text": "Draft"}])

    mock.close()
    mock.close()
    scripted.close()
    scripted.close()

    assert mock.close_count == 1
    assert scripted.close_count == 1
