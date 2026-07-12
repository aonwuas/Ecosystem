"""Read-only registry for MVP response strategies."""

from __future__ import annotations

from types import MappingProxyType

from prompt_orchestrator.domain.enums import OutputMode, StrategyId
from prompt_orchestrator.exceptions import PromptRenderError
from prompt_orchestrator.strategies.definitions import StrategyDefinition

MARKDOWN_TEXT_JSON = frozenset({OutputMode.TEXT, OutputMode.MARKDOWN, OutputMode.JSON})
TEXT_MARKDOWN = frozenset({OutputMode.TEXT, OutputMode.MARKDOWN})


def _definition(
    strategy_id: StrategyId,
    description: str,
    criteria: tuple[str, ...],
    *,
    modes: frozenset[OutputMode] = TEXT_MARKDOWN,
    critic_recommended: bool = True,
    requires_empathy: bool = False,
    requires_caution: bool = False,
) -> StrategyDefinition:
    return StrategyDefinition(
        strategy_id=strategy_id,
        description=description,
        template_name=f"strategies/{strategy_id.value}.md",
        supported_output_modes=modes,
        default_quality_criteria=criteria,
        critic_recommended=critic_recommended,
        requires_empathy=requires_empathy,
        requires_caution=requires_caution,
    )


_REGISTRY = {
    StrategyId.DIRECT_ANSWER: _definition(
        StrategyId.DIRECT_ANSWER,
        "Answer directly with minimal scaffolding.",
        ("Answer the task directly.", "State material assumptions."),
    ),
    StrategyId.CONCISE_EXPLANATION: _definition(
        StrategyId.CONCISE_EXPLANATION,
        "Explain clearly and briefly.",
        ("Keep the explanation brief.", "Use plain language."),
    ),
    StrategyId.STEP_BY_STEP_EXPLANATION: _definition(
        StrategyId.STEP_BY_STEP_EXPLANATION,
        "Organize a teachable sequence.",
        ("Provide ordered steps.", "Explain transitions clearly."),
    ),
    StrategyId.STRUCTURED_ANALYSIS: _definition(
        StrategyId.STRUCTURED_ANALYSIS,
        "Separate facts, assumptions, considerations, and conclusions.",
        ("Separate assumptions from conclusions.", "Make tradeoffs explicit."),
        modes=MARKDOWN_TEXT_JSON,
    ),
    StrategyId.PLANNING: _definition(
        StrategyId.PLANNING,
        "Produce a staged actionable plan.",
        ("Include dependencies.", "Define completion criteria."),
    ),
    StrategyId.COMPARISON: _definition(
        StrategyId.COMPARISON,
        "Compare options on explicit criteria.",
        ("Use explicit criteria.", "Explain tradeoffs."),
    ),
    StrategyId.DECISION_SUPPORT: _definition(
        StrategyId.DECISION_SUPPORT,
        "Provide a conditional recommendation.",
        ("Avoid false certainty.", "State decision criteria."),
    ),
    StrategyId.BRAINSTORMING: _definition(
        StrategyId.BRAINSTORMING,
        "Generate diverse useful options and organize them.",
        ("Generate varied options.", "Group related ideas."),
    ),
    StrategyId.DRAFT_GENERATION: _definition(
        StrategyId.DRAFT_GENERATION,
        "Produce finished reusable text in the requested format.",
        ("Match the requested format.", "Produce polished final text."),
    ),
    StrategyId.REWRITE_PRESERVE_MEANING: _definition(
        StrategyId.REWRITE_PRESERVE_MEANING,
        "Preserve facts and intent while changing requested qualities.",
        ("Preserve meaning.", "Apply the requested transformation."),
    ),
    StrategyId.SUMMARIZATION: _definition(
        StrategyId.SUMMARIZATION,
        "Preserve key points and uncertainty without adding facts.",
        ("Preserve key points.", "Do not add unsupported facts."),
    ),
    StrategyId.INFORMATION_EXTRACTION: _definition(
        StrategyId.INFORMATION_EXTRACTION,
        "Return only information supported by supplied text.",
        ("Extract only supported information.", "Avoid inference beyond text."),
        modes=MARKDOWN_TEXT_JSON,
    ),
    StrategyId.STRUCTURED_OUTPUT: _definition(
        StrategyId.STRUCTURED_OUTPUT,
        "Obey the supported schema or format stated in the output contract.",
        ("Follow the requested schema.", "Return valid structured output."),
        modes=MARKDOWN_TEXT_JSON,
    ),
    StrategyId.CREATIVE_GENERATION: _definition(
        StrategyId.CREATIVE_GENERATION,
        "Satisfy creative constraints while maintaining coherence.",
        ("Honor creative constraints.", "Maintain internal coherence."),
        critic_recommended=False,
    ),
    StrategyId.EMPATHETIC_GUIDANCE: _definition(
        StrategyId.EMPATHETIC_GUIDANCE,
        "Be supportive, avoid overclaiming, and offer practical next steps.",
        ("Use supportive language.", "Offer practical next steps."),
        requires_empathy=True,
    ),
    StrategyId.TECHNICAL_ASSISTANCE: _definition(
        StrategyId.TECHNICAL_ASSISTANCE,
        "Provide technically precise guidance and validation steps.",
        ("Be technically precise.", "Include validation steps."),
    ),
    StrategyId.SAFETY_REDIRECT: _definition(
        StrategyId.SAFETY_REDIRECT,
        "Explain boundaries and offer safer relevant help.",
        ("Set clear boundaries.", "Offer safer alternatives."),
        requires_caution=True,
    ),
}

STRATEGY_REGISTRY = MappingProxyType(_REGISTRY)


def get_strategy(strategy_id: StrategyId | str) -> StrategyDefinition:
    """Return a registered strategy or fail clearly."""
    try:
        normalized = StrategyId(strategy_id)
    except ValueError as exc:
        raise PromptRenderError(
            f"Unknown strategy '{strategy_id}'.",
            code="STRATEGY_UNKNOWN",
        ) from exc
    try:
        return STRATEGY_REGISTRY[normalized]
    except KeyError as exc:
        raise PromptRenderError(
            f"Unknown strategy '{normalized.value}'.",
            code="STRATEGY_UNKNOWN",
        ) from exc


def strategy_registry_summary() -> str:
    """Return a stable summary for understanding prompts."""
    lines = []
    for strategy_id in sorted(STRATEGY_REGISTRY, key=lambda item: item.value):
        definition = STRATEGY_REGISTRY[strategy_id]
        modes = ", ".join(
            sorted(mode.value for mode in definition.supported_output_modes)
        )
        lines.append(f"- {strategy_id.value}: {definition.description} Modes: {modes}.")
    return "\n".join(lines)
