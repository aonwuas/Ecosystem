from __future__ import annotations

import pytest

from prompt_orchestrator.domain.enums import OutputMode, StrategyId
from prompt_orchestrator.exceptions import PromptRenderError
from prompt_orchestrator.prompts import (
    COMMON_WORKER_VARIABLES,
    CRITIC_VARIABLES,
    REVISION_VARIABLES,
    UNDERSTANDING_VARIABLES,
    load_template,
    render_template,
)
from prompt_orchestrator.strategies import (
    STRATEGY_REGISTRY,
    get_strategy,
    strategy_registry_summary,
)


def worker_values(strategy_id: StrategyId = StrategyId.COMPARISON) -> dict[str, str]:
    definition = get_strategy(strategy_id)
    return {
        "strategy_id": strategy_id.value,
        "strategy_description": definition.description,
        "user_goal": "Choose a database.",
        "execution_plan_summary": "Compare SQLite and PostgreSQL.",
        "assumptions": "Small team, unknown workload.",
        "uncertainties": "Expected concurrency is unknown.",
        "must_include": "Tradeoffs and conditional recommendation.",
        "must_avoid": "Do not pretend workload is known.",
        "output_contract": "Markdown comparison.",
        "quality_criteria": "State assumptions.",
        "user_request": "Help me choose between SQLite and PostgreSQL.",
        "caller_context": "Building a small app.",
    }


def test_registry_contains_every_mvp_strategy() -> None:
    assert set(STRATEGY_REGISTRY) == set(StrategyId)


def test_every_registered_strategy_has_worker_template() -> None:
    for strategy_id, definition in STRATEGY_REGISTRY.items():
        template = load_template(definition.template_name)
        rendered = render_template(
            template,
            worker_values(strategy_id),
            allowed_variables=COMMON_WORKER_VARIABLES,
        )

        assert f"Strategy: {strategy_id.value}" in rendered
        assert "<USER_REQUEST>" in rendered
        assert "</USER_REQUEST>" in rendered
        assert "<CALLER_CONTEXT>" in rendered
        assert "</CALLER_CONTEXT>" in rendered


def test_registry_metadata_contains_supported_modes_and_quality_criteria() -> None:
    comparison = get_strategy(StrategyId.COMPARISON)
    structured = get_strategy(StrategyId.STRUCTURED_OUTPUT)
    creative = get_strategy(StrategyId.CREATIVE_GENERATION)

    assert OutputMode.MARKDOWN in comparison.supported_output_modes
    assert OutputMode.JSON in structured.supported_output_modes
    assert comparison.default_quality_criteria
    assert creative.critic_recommended is False


def test_unknown_strategy_is_rejected() -> None:
    with pytest.raises(PromptRenderError, match="Unknown strategy"):
        get_strategy("not_registered")


def test_strategy_registry_summary_is_stable_and_bounded() -> None:
    summary = strategy_registry_summary()

    assert "comparison" in summary
    assert "technical_assistance" in summary
    assert "openai" not in summary.lower()


def test_template_loader_rejects_paths_outside_package() -> None:
    for name in ("../README.md", "/tmp/template.md", "strategies/../../README.md"):
        with pytest.raises(PromptRenderError):
            load_template(name)


def test_unknown_template_is_rejected() -> None:
    with pytest.raises(PromptRenderError, match="Unknown"):
        load_template("strategies/not_registered.md")


def test_renderer_rejects_missing_variables() -> None:
    with pytest.raises(PromptRenderError, match="Missing"):
        render_template(
            "Hello $name from $place",
            {"name": "Ada"},
            allowed_variables=frozenset({"name", "place"}),
        )


def test_renderer_rejects_disallowed_template_placeholders() -> None:
    with pytest.raises(PromptRenderError, match="disallowed"):
        render_template(
            "Hello $name",
            {"name": "Ada"},
            allowed_variables=frozenset({"place"}),
        )


def test_renderer_rejects_unexpected_values() -> None:
    with pytest.raises(PromptRenderError, match="Unexpected"):
        render_template(
            "Hello $name",
            {"name": "Ada", "place": "Lovelace"},
            allowed_variables=frozenset({"name"}),
        )


def test_understanding_template_has_contract_and_delimiters() -> None:
    template = load_template("understanding.md")
    rendered = render_template(
        template,
        {
            "user_request": "Summarize this.",
            "caller_context": "Context text.",
            "requested_output_mode": "markdown",
            "strategy_registry": strategy_registry_summary(),
            "execution_plan_schema": "ExecutionPlan fields.",
            "clarification_policy": "Ask only when needed.",
        },
        allowed_variables=UNDERSTANDING_VARIABLES,
    )

    assert "Contract version: 1" in rendered
    assert "return exactly one JSON object".lower() in rendered.lower()
    assert "<USER_REQUEST>" in rendered
    assert "<CALLER_CONTEXT>" in rendered


def test_critic_and_revision_templates_render_structural_sections() -> None:
    critic = render_template(
        load_template("critic.md"),
        {
            "original_request": "Original",
            "caller_context": "Context",
            "execution_plan": "Plan",
            "draft": "Draft",
            "quality_criteria": "Criteria",
        },
        allowed_variables=CRITIC_VARIABLES,
    )
    revision = render_template(
        load_template("revision.md"),
        {
            "original_request": "Original",
            "caller_context": "Context",
            "execution_plan": "Plan",
            "draft": "Draft",
            "critic_issues": "Issues",
            "revision_instruction": "Fix issues.",
        },
        allowed_variables=REVISION_VARIABLES,
    )

    assert "<DRAFT>" in critic
    assert "<QUALITY_CRITERIA>" in critic
    assert "<REVISION_INSTRUCTION>" in revision


def test_templates_do_not_request_hidden_chain_of_thought() -> None:
    template_names = ["understanding.md", "critic.md", "revision.md"]
    template_names.extend(
        definition.template_name for definition in STRATEGY_REGISTRY.values()
    )

    for template_name in template_names:
        text = load_template(template_name).lower()
        assert "chain-of-thought" not in text
        assert "hidden reasoning" not in text
        assert "detailed reasoning" not in text


def test_worker_render_inserts_user_content_only_in_delimited_sections() -> None:
    rendered = render_template(
        load_template("strategies/comparison.md"),
        worker_values(),
        allowed_variables=COMMON_WORKER_VARIABLES,
    )

    user_text = "Help me choose between SQLite and PostgreSQL."
    assert rendered.count(user_text) == 1
    assert f"<USER_REQUEST>\n{user_text}\n</USER_REQUEST>" in rendered
