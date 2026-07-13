"""Shared redaction helpers for known secret values and sensitive keys."""

from __future__ import annotations

from prompt_orchestrator.domain._base import JsonValue

SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "secret",
    "token",
    "password",
)

_KNOWN_SECRET_VALUES: set[str] = set()


def register_known_secret(value: str | None) -> None:
    """Remember a concrete secret value for later redaction."""
    if value:
        _KNOWN_SECRET_VALUES.add(value)


def known_secret_values() -> frozenset[str]:
    """Return known concrete secret values loaded in this process."""
    return frozenset(_KNOWN_SECRET_VALUES)


def is_sensitive_key(key: str) -> bool:
    """Return whether a key name commonly carries secret material."""
    lowered = key.lower().replace("-", "_")
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def redact_known_secrets(text: str) -> str:
    """Redact exact known secret values inside a string."""
    redacted = text
    for secret in sorted(_KNOWN_SECRET_VALUES, key=len, reverse=True):
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def redact_value(value: JsonValue) -> JsonValue:
    """Redact known secret values recursively in JSON-compatible values."""
    if isinstance(value, str):
        return redact_known_secrets(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if is_sensitive_key(key) else redact_value(item)
            for key, item in value.items()
        }
    return value
