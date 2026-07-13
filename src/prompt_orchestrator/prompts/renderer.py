"""Render prompt templates with explicit variable allow-lists."""

from __future__ import annotations

from collections.abc import Mapping
from string import Template

from prompt_orchestrator.exceptions import PromptRenderError

UNDERSTANDING_VARIABLES = frozenset(
    {
        "user_request",
        "caller_context",
        "requested_output_mode",
        "strategy_registry",
        "execution_plan_schema",
        "clarification_policy",
    }
)
COMMON_WORKER_VARIABLES = frozenset(
    {
        "strategy_id",
        "strategy_description",
        "user_goal",
        "execution_plan_summary",
        "assumptions",
        "uncertainties",
        "must_include",
        "must_avoid",
        "output_contract",
        "quality_criteria",
        "user_request",
        "caller_context",
    }
)
CRITIC_VARIABLES = frozenset(
    {
        "original_request",
        "caller_context",
        "execution_plan",
        "draft",
        "quality_criteria",
    }
)
REVISION_VARIABLES = frozenset(
    {
        "original_request",
        "caller_context",
        "execution_plan",
        "draft",
        "critic_issues",
        "revision_instruction",
    }
)


def render_template(
    template_text: str,
    values: Mapping[str, object],
    *,
    allowed_variables: frozenset[str],
) -> str:
    """Render a template after validating placeholders and supplied variables."""
    placeholders = _template_placeholders(template_text)
    disallowed_placeholders = placeholders - allowed_variables
    if disallowed_placeholders:
        names = ", ".join(sorted(disallowed_placeholders))
        raise PromptRenderError(
            f"Template contains disallowed placeholders: {names}.",
            code="PROMPT_TEMPLATE_VARIABLE_DISALLOWED",
        )

    missing = placeholders - set(values)
    if missing:
        names = ", ".join(sorted(missing))
        raise PromptRenderError(
            f"Missing template variables: {names}.",
            code="PROMPT_TEMPLATE_VARIABLE_MISSING",
        )

    extra = set(values) - allowed_variables
    if extra:
        names = ", ".join(sorted(extra))
        raise PromptRenderError(
            f"Unexpected template variables: {names}.",
            code="PROMPT_TEMPLATE_VARIABLE_UNKNOWN",
        )

    safe_values = {key: str(value) for key, value in values.items()}
    try:
        return Template(template_text).substitute(safe_values)
    except (KeyError, ValueError) as exc:
        raise PromptRenderError(
            "Prompt template rendering failed.",
            code="PROMPT_TEMPLATE_RENDER_FAILED",
        ) from exc


def _template_placeholders(template_text: str) -> frozenset[str]:
    names: set[str] = set()
    for match in Template.pattern.finditer(template_text):
        named = match.group("named") or match.group("braced")
        invalid = match.group("invalid")
        if invalid is not None:
            raise PromptRenderError(
                "Template contains an invalid placeholder.",
                code="PROMPT_TEMPLATE_INVALID",
            )
        if named:
            names.add(named)
    return frozenset(names)
