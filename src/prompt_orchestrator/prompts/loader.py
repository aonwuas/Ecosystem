"""Load package-controlled prompt templates."""

from __future__ import annotations

from importlib import resources
from pathlib import PurePosixPath

from prompt_orchestrator.exceptions import PromptRenderError

TEMPLATE_PACKAGE = "prompt_orchestrator.templates"


def load_template(template_name: str) -> str:
    """Load a template by package-relative name."""
    path = PurePosixPath(template_name)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".md":
        raise PromptRenderError(
            f"Template name '{template_name}' is not allowed.",
            code="PROMPT_TEMPLATE_NAME_INVALID",
        )
    try:
        template = resources.files(TEMPLATE_PACKAGE).joinpath(*path.parts)
        if not template.is_file():
            raise FileNotFoundError(template_name)
        return template.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise PromptRenderError(
            f"Unknown prompt template '{template_name}'.",
            code="PROMPT_TEMPLATE_UNKNOWN",
        ) from exc
