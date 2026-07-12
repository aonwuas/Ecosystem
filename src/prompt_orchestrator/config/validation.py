"""Configuration validation and sanitized summaries."""

from __future__ import annotations

from prompt_orchestrator.config.models import ConfigSummary, PromptOrchestratorConfig


def summarize_config(config: PromptOrchestratorConfig) -> ConfigSummary:
    """Build a sanitized summary that never includes resolved secret values."""
    runtime = config.runtime
    return ConfigSummary(
        path=str(config.path) if config.path is not None else "<memory>",
        providers=sorted(str(name) for name in config.providers),
        models=sorted(str(name) for name in config.models),
        roles={
            "understanding": config.roles.understanding,
            "worker": config.roles.worker,
            "critic": config.roles.critic,
            "revision": config.roles.revision,
        },
        runtime={
            "structured_output_repair_attempts": (
                runtime.structured_output_repair_attempts
            ),
            "transient_http_retries": runtime.transient_http_retries,
            "enable_critic": runtime.enable_critic,
            "strict_critic": runtime.strict_critic,
            "enable_revision": runtime.enable_revision,
            "max_revision_attempts": runtime.max_revision_attempts,
            "understanding_failure_mode": runtime.understanding_failure_mode.value,
            "default_output_mode": runtime.default_output_mode.value,
        },
    )
