"""YAML configuration loading."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.exceptions import ConfigurationError

CONFIG_ENV_VAR = "PROMPT_ORCHESTRATOR_CONFIG"


def find_config_path(start_dir: Path | None = None) -> Path:
    """Find a configuration file using the documented search order."""
    env_path = os.environ.get(CONFIG_ENV_VAR)
    if env_path:
        path = Path(env_path)
        if path.is_file():
            return path
        raise ConfigurationError(
            f"{CONFIG_ENV_VAR} points to missing config file '{path}'.",
            code="CONFIG_NOT_FOUND",
        )

    root = start_dir or Path.cwd()
    for filename in ("config.local.yaml", "config.yaml"):
        candidate = root / filename
        if candidate.is_file():
            return candidate

    raise ConfigurationError(
        "No configuration file found. Provide --config or create config.local.yaml.",
        code="CONFIG_NOT_FOUND",
    )


def load_config(config_path: Path | str | None = None) -> PromptOrchestratorConfig:
    """Load and validate runtime configuration."""
    path = Path(config_path) if config_path is not None else find_config_path()
    return load_config_from_path(path)


def load_config_from_path(path: Path) -> PromptOrchestratorConfig:
    """Load and validate a specific YAML configuration path."""
    if not path.is_file():
        raise ConfigurationError(
            f"Configuration file '{path}' does not exist.",
            code="CONFIG_NOT_FOUND",
        )

    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(
            f"Could not read configuration file '{path}'.",
            code="CONFIG_READ_FAILED",
        ) from exc

    try:
        raw_data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"Configuration file '{path}' is not valid YAML.",
            code="CONFIG_YAML_INVALID",
        ) from exc

    if raw_data is None:
        raw_data = {}
    if not isinstance(raw_data, dict):
        raise ConfigurationError(
            "Configuration root must be a mapping.",
            code="CONFIG_INVALID",
        )

    try:
        config = PromptOrchestratorConfig.model_validate(cast(dict[str, Any], raw_data))
    except ValidationError as exc:
        raise ConfigurationError(
            _validation_error_message(exc),
            code="CONFIG_INVALID",
        ) from exc

    return config.model_copy(update={"path": path})


def _validation_error_message(error: ValidationError) -> str:
    first_error = error.errors(include_url=False)[0]
    location = ".".join(str(part) for part in first_error["loc"])
    message = str(first_error["msg"])
    if location:
        return f"Invalid configuration at '{location}': {message}"
    return f"Invalid configuration: {message}"
