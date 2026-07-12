"""Prompt template loading and rendering."""

from prompt_orchestrator.prompts.loader import load_template
from prompt_orchestrator.prompts.renderer import (
    COMMON_WORKER_VARIABLES,
    CRITIC_VARIABLES,
    REVISION_VARIABLES,
    UNDERSTANDING_VARIABLES,
    render_template,
)

__all__ = [
    "COMMON_WORKER_VARIABLES",
    "CRITIC_VARIABLES",
    "REVISION_VARIABLES",
    "UNDERSTANDING_VARIABLES",
    "load_template",
    "render_template",
]
