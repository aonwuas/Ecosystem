"""Pydantic configuration models and role resolution."""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_validator,
)

from prompt_orchestrator.domain._base import JsonObject, JsonValue
from prompt_orchestrator.domain.enums import ModelRole, OutputMode, StrategyId
from prompt_orchestrator.redaction import is_sensitive_key, register_known_secret

ConfigName = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9_.-]+$",
    ),
]
HeaderMap = Annotated[dict[str, str], Field(default_factory=dict, max_length=50)]


class ConfigModel(BaseModel):
    """Base class for immutable configuration models."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


class SecretValue:
    """Resolved secret value that redacts all normal representations."""

    def __init__(self, value: str) -> None:
        if value == "":
            raise ValueError("secret value must not be empty")
        self._value = value

    def reveal(self) -> str:
        """Return the raw secret for provider boundary code."""
        return self._value

    def __repr__(self) -> str:
        return "SecretValue(********)"

    def __str__(self) -> str:
        return "********"


class SecretHeaderConfig(ConfigModel):
    """Environment-backed HTTP header secret."""

    env: ConfigName
    value: SecretValue | None = Field(default=None, exclude=True, repr=False)

    @model_validator(mode="after")
    def resolve_value(self) -> Self:
        secret_value = os.environ.get(self.env)
        if secret_value is None or secret_value == "":
            raise ValueError(
                f"secret header env '{self.env}' is set but the environment "
                "variable is missing"
            )
        register_known_secret(secret_value)
        object.__setattr__(self, "value", SecretValue(secret_value))
        return self

    @field_serializer("value")
    def serialize_value(self, value: SecretValue | None) -> None:
        return None


class ProviderType(StrEnum):
    MOCK = "mock"
    OPENAI_COMPATIBLE = "openai_compatible"


class OpenAICompatibleProviderConfig(ConfigModel):
    """Transport configuration for OpenAI-compatible chat-completions APIs."""

    type: Literal["openai_compatible"]
    base_url: str
    api_key_env: ConfigName | None = None
    default_headers: HeaderMap = Field(default_factory=dict)
    secret_headers: dict[ConfigName, SecretHeaderConfig] = Field(
        default_factory=dict,
        max_length=50,
    )
    verify_tls: bool = Field(default=True, strict=True)
    api_key: SecretValue | None = Field(default=None, exclude=True, repr=False)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return normalized

    @field_validator("default_headers")
    @classmethod
    def validate_header_values(cls, value: dict[str, str]) -> dict[str, str]:
        for header_name, header_value in value.items():
            if not header_name.strip() or not header_value.strip():
                raise ValueError("default_headers keys and values must be non-empty")
            if is_sensitive_key(header_name):
                raise ValueError(
                    f"default_headers contains sensitive header '{header_name}'; "
                    "use secret_headers with an environment variable"
                )
        return value

    @model_validator(mode="after")
    def resolve_api_key(self) -> Self:
        if self.api_key_env is None:
            return self
        secret_value = os.environ.get(self.api_key_env)
        if secret_value is None or secret_value == "":
            raise ValueError(
                f"api_key_env '{self.api_key_env}' is set but the environment "
                "variable is missing"
            )
        register_known_secret(secret_value)
        object.__setattr__(self, "api_key", SecretValue(secret_value))
        return self

    @field_serializer("api_key")
    def serialize_api_key(self, value: SecretValue | None) -> None:
        return None


class MockProviderConfig(ConfigModel):
    """Configuration for deterministic mock/scripted model providers."""

    type: Literal["mock"]
    fixture_path: str

    @field_validator("fixture_path")
    @classmethod
    def validate_fixture_path(cls, value: str) -> str:
        normalized = value.strip()
        if normalized == "":
            raise ValueError("fixture_path must be non-empty")
        return normalized


ProviderConfig = Annotated[
    OpenAICompatibleProviderConfig | MockProviderConfig,
    Field(discriminator="type"),
]


class ModelConfig(ConfigModel):
    """Named model defaults and provider reference."""

    provider: ConfigName
    model: str = Field(min_length=1, max_length=200)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0, strict=True)
    max_output_tokens: int = Field(default=4096, gt=0, le=131_072, strict=True)
    timeout_seconds: int = Field(default=180, gt=0, le=3600, strict=True)
    extra_body: JsonObject = Field(default_factory=dict)
    metadata: JsonObject = Field(default_factory=dict)


class RoleBindings(ConfigModel):
    """Required MVP model bindings for every logical role."""

    understanding: ConfigName
    worker: ConfigName
    critic: ConfigName
    revision: ConfigName

    def model_for_role(self, role: ModelRole) -> str:
        """Return the configured model name for a logical role."""
        return str(getattr(self, role.value))


class UnderstandingFailureMode(StrEnum):
    CLARIFY = "clarify"


class TraceConfig(ConfigModel):
    """Runtime trace rendering policy."""

    enabled_by_default: bool = Field(default=False, strict=True)


class StrategyOverride(ConfigModel):
    """Bounded per-strategy runtime override settings."""

    enable_critic: bool | None = Field(default=None)
    enable_revision: bool | None = Field(default=None)


class RuntimeConfig(ConfigModel):
    """Runtime retry, critic, revision, fallback, and trace settings."""

    structured_output_repair_attempts: int = Field(default=1, ge=0, le=1, strict=True)
    transient_http_retries: int = Field(default=1, ge=0, le=1, strict=True)
    enable_critic: bool = Field(default=True, strict=True)
    strict_critic: bool = Field(default=False, strict=True)
    enable_revision: bool = Field(default=True, strict=True)
    max_revision_attempts: int = Field(default=1, ge=0, le=1, strict=True)
    understanding_failure_mode: UnderstandingFailureMode = (
        UnderstandingFailureMode.CLARIFY
    )
    default_output_mode: OutputMode = OutputMode.TEXT
    strategy_overrides: dict[StrategyId, StrategyOverride] = Field(
        default_factory=dict,
        max_length=20,
    )
    trace: TraceConfig = Field(default_factory=TraceConfig)


class ResolvedModel(ConfigModel):
    """Resolved role binding through model and provider configuration."""

    role: ModelRole
    model_name: str
    model: ModelConfig
    provider_name: str
    provider: ProviderConfig


class PromptOrchestratorConfig(ConfigModel):
    """Complete validated runtime configuration."""

    version: Literal[1]
    providers: dict[ConfigName, ProviderConfig] = Field(min_length=1, max_length=50)
    models: dict[ConfigName, ModelConfig] = Field(min_length=1, max_length=100)
    roles: RoleBindings
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    path: Path | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        for model_name, model in self.models.items():
            if model.provider not in self.providers:
                raise ValueError(
                    f"model '{model_name}' references unknown provider "
                    f"'{model.provider}'"
                )
        for role in ModelRole:
            model_name = self.roles.model_for_role(role)
            if model_name not in self.models:
                raise ValueError(
                    f"role '{role.value}' references unknown model '{model_name}'"
                )
        return self

    @field_validator("providers", "models")
    @classmethod
    def validate_config_names(
        cls,
        value: dict[str, object],
        info: ValidationInfo,
    ) -> dict[str, object]:
        for key in value:
            if not key.strip():
                raise ValueError(f"{info.field_name} names must be non-empty")
        return value

    def resolve_role(self, role: ModelRole) -> ResolvedModel:
        """Resolve role -> named model -> provider."""
        model_name = self.roles.model_for_role(role)
        model = self.models[model_name]
        provider = self.providers[model.provider]
        return ResolvedModel(
            role=role,
            model_name=model_name,
            model=model,
            provider_name=model.provider,
            provider=provider,
        )


class ConfigSummary(ConfigModel):
    """Sanitized configuration summary for CLI validation output."""

    path: str
    providers: list[str]
    models: list[str]
    roles: dict[str, str]
    runtime: dict[str, JsonValue]
