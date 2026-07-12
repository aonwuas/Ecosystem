from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from prompt_orchestrator.config import (
    find_config_path,
    load_config,
    load_config_from_path,
    summarize_config,
)
from prompt_orchestrator.domain.enums import ModelRole
from prompt_orchestrator.exceptions import ConfigurationError

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def write_config(tmp_path: Path, content: str, name: str = "config.yaml") -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_config_example_validates_and_summarizes_without_secret_values() -> None:
    config = load_config_from_path(REPOSITORY_ROOT / "config.example.yaml")
    summary = summarize_config(config)

    assert summary.providers == ["local_llama_server"]
    assert summary.models == ["local_general"]
    assert summary.roles["understanding"] == "local_general"
    assert "api_key" not in summary.model_dump_json()


def test_role_resolution_returns_model_and_provider() -> None:
    config = load_config_from_path(REPOSITORY_ROOT / "config.example.yaml")

    resolved = config.resolve_role(ModelRole.WORKER)

    assert resolved.role is ModelRole.WORKER
    assert resolved.model_name == "local_general"
    assert resolved.provider_name == "local_llama_server"
    assert resolved.provider.type == "openai_compatible"


def test_missing_provider_reference_fails_before_network_use(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
version: 1
providers:
  local:
    type: openai_compatible
    base_url: http://127.0.0.1:8080/v1
models:
  local_general:
    provider: missing_provider
    model: local-model
roles:
  understanding: local_general
  worker: local_general
  critic: local_general
  revision: local_general
runtime: {}
""",
    )

    with pytest.raises(ConfigurationError, match="unknown provider"):
        load_config_from_path(path)


def test_missing_role_model_reference_fails_before_network_use(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
version: 1
providers:
  local:
    type: openai_compatible
    base_url: http://127.0.0.1:8080/v1
models:
  local_general:
    provider: local
    model: local-model
roles:
  understanding: local_general
  worker: missing_model
  critic: local_general
  revision: local_general
runtime: {}
""",
    )

    with pytest.raises(ConfigurationError, match="unknown model"):
        load_config_from_path(path)


def test_optional_local_api_key_may_be_absent(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
version: 1
providers:
  local:
    type: openai_compatible
    base_url: http://127.0.0.1:8080/v1
    api_key_env: null
models:
  local_general:
    provider: local
    model: local-model
roles:
  understanding: local_general
  worker: local_general
  critic: local_general
  revision: local_general
runtime: {}
""",
    )

    config = load_config_from_path(path)

    assert config.providers["local"].type == "openai_compatible"


def test_required_missing_environment_key_fails_without_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROMPT_ORCHESTRATOR_TEST_KEY", raising=False)
    path = write_config(
        tmp_path,
        """
version: 1
providers:
  hosted:
    type: openai_compatible
    base_url: https://api.example.test/v1
    api_key_env: PROMPT_ORCHESTRATOR_TEST_KEY
models:
  hosted_general:
    provider: hosted
    model: hosted-model
roles:
  understanding: hosted_general
  worker: hosted_general
  critic: hosted_general
  revision: hosted_general
runtime: {}
""",
    )

    with pytest.raises(ConfigurationError) as error:
        load_config_from_path(path)

    message = str(error.value)
    assert "PROMPT_ORCHESTRATOR_TEST_KEY" in message
    assert "secret-value" not in message


def test_resolved_environment_key_is_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROMPT_ORCHESTRATOR_TEST_KEY", "secret-value")
    path = write_config(
        tmp_path,
        """
version: 1
providers:
  hosted:
    type: openai_compatible
    base_url: https://api.example.test/v1/
    api_key_env: PROMPT_ORCHESTRATOR_TEST_KEY
models:
  hosted_general:
    provider: hosted
    model: hosted-model
roles:
  understanding: hosted_general
  worker: hosted_general
  critic: hosted_general
  revision: hosted_general
runtime: {}
""",
    )

    config = load_config_from_path(path)
    provider = config.providers["hosted"]

    assert provider.type == "openai_compatible"
    assert provider.base_url == "https://api.example.test/v1"
    assert "secret-value" not in repr(provider)
    assert "secret-value" not in config.model_dump_json()


def test_runtime_bounds_and_unknown_keys_are_rejected(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
version: 1
providers:
  scripted:
    type: mock
    fixture_path: tests/fixtures/scripted_models.yaml
models:
  scripted_general:
    provider: scripted
    model: scripted-model
roles:
  understanding: scripted_general
  worker: scripted_general
  critic: scripted_general
  revision: scripted_general
runtime:
  transient_http_retries: 2
extra_top_level: true
""",
    )

    with pytest.raises(ConfigurationError, match="extra_top_level|transient"):
        load_config_from_path(path)


def test_search_order_uses_env_then_local_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    explicit_path = write_config(tmp_path, "version: 1\n", "explicit.yaml")
    monkeypatch.setenv("PROMPT_ORCHESTRATOR_CONFIG", str(explicit_path))

    assert find_config_path(tmp_path) == explicit_path

    monkeypatch.delenv("PROMPT_ORCHESTRATOR_CONFIG")
    local_path = write_config(tmp_path, "version: 1\n", "config.local.yaml")
    write_config(tmp_path, "version: 1\n", "config.yaml")

    assert find_config_path(tmp_path) == local_path


def test_load_config_uses_search_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = write_config(
        tmp_path,
        """
version: 1
providers:
  scripted:
    type: mock
    fixture_path: tests/fixtures/scripted_models.yaml
models:
  scripted_general:
    provider: scripted
    model: scripted-model
roles:
  understanding: scripted_general
  worker: scripted_general
  critic: scripted_general
  revision: scripted_general
runtime: {}
""",
        "config.local.yaml",
    )
    monkeypatch.chdir(tmp_path)

    assert load_config().path == path


def test_config_validate_cli_succeeds_for_example() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "prompt_orchestrator",
            "config",
            "validate",
            "--config",
            str(REPOSITORY_ROOT / "config.example.yaml"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Configuration valid." in result.stdout
    assert "local_llama_server" in result.stdout
    assert "api_key" not in result.stdout


def test_config_validate_cli_fails_concisely_for_invalid_file(tmp_path: Path) -> None:
    invalid_path = write_config(tmp_path, "version: 1\n")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "prompt_orchestrator",
            "config",
            "validate",
            "--config",
            str(invalid_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "Error [CONFIG_INVALID]" in result.stderr
    assert "Traceback" not in result.stderr
