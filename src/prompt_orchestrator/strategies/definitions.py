"""Static strategy metadata."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_orchestrator.domain.enums import OutputMode, StrategyId


@dataclass(frozen=True)
class StrategyDefinition:
    """Package-controlled metadata for one response strategy."""

    strategy_id: StrategyId
    description: str
    template_name: str
    supported_output_modes: frozenset[OutputMode]
    default_quality_criteria: tuple[str, ...]
    critic_recommended: bool = True
    requires_empathy: bool = False
    requires_caution: bool = False
