"""Deterministic execution-plan policy and clarification gate."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import (
    ClarificationDecision,
    ExecutionPlan,
    OutputContract,
    PromptRequest,
    TaskUnderstanding,
    ValidatedExecutionPlan,
)
from prompt_orchestrator.domain._base import MAX_LIST_ITEMS
from prompt_orchestrator.domain.enums import (
    ClarificationAction,
    OutputMode,
    RiskLevel,
    StrategyId,
    TaskComplexity,
)
from prompt_orchestrator.exceptions import ExecutionPlanValidationError, PolicyError
from prompt_orchestrator.strategies import STRATEGY_REGISTRY, StrategyDefinition


class PolicyOutcome(StrEnum):
    """Deterministic gate outcome after policy evaluation."""

    PROCEED = "proceed"
    CLARIFICATION_REQUIRED = "clarification_required"
    REFUSED = "refused"


@dataclass(frozen=True)
class PolicyEvaluation:
    """Policy-evaluated plan and gate outcome."""

    validated_plan: ValidatedExecutionPlan
    outcome: PolicyOutcome


def evaluate_execution_plan_policy(
    plan: ExecutionPlan,
    *,
    request: PromptRequest,
    config: PromptOrchestratorConfig,
    used_safe_fallback: bool = False,
    registry: Mapping[StrategyId, StrategyDefinition] = STRATEGY_REGISTRY,
) -> PolicyEvaluation:
    """Apply deterministic policy before any plan can proceed to execution."""
    changes: list[str] = []
    warnings: list[str] = []

    strategy = _registered_strategy(plan.strategy, registry)
    output_contract = _apply_output_mode_policy(
        plan=plan,
        request=request,
        strategy=strategy,
        changes=changes,
    )
    clarification = _apply_clarification_policy(plan.clarification, changes)
    critic_required = _apply_critic_policy(
        plan=plan,
        strategy=strategy,
        config=config,
        changes=changes,
    )

    must_include = _normalize_string_list(
        plan.must_include,
        field_name="must_include",
        changes=changes,
    )
    must_avoid = _normalize_string_list(
        plan.must_avoid,
        field_name="must_avoid",
        changes=changes,
    )
    quality_criteria = _normalize_string_list(
        plan.quality_criteria,
        field_name="quality_criteria",
        changes=changes,
    )

    policy_plan = ExecutionPlan(
        schema_version=plan.schema_version,
        understanding=_normalize_understanding(plan.understanding, changes),
        clarification=clarification,
        strategy=plan.strategy,
        output_contract=output_contract,
        must_include=must_include,
        must_avoid=must_avoid,
        quality_criteria=quality_criteria,
        critic_required=critic_required,
    )

    outcome = _outcome_for(policy_plan.clarification.action)
    if used_safe_fallback:
        warnings.append("understanding model output could not be validated")

    return PolicyEvaluation(
        validated_plan=ValidatedExecutionPlan(
            plan=policy_plan,
            policy_changes=changes,
            validation_warnings=warnings,
            used_safe_fallback=used_safe_fallback,
        ),
        outcome=outcome,
    )


def _registered_strategy(
    strategy_id: StrategyId,
    registry: Mapping[StrategyId, StrategyDefinition],
) -> StrategyDefinition:
    if not isinstance(strategy_id, StrategyId):
        raise ExecutionPlanValidationError(
            "Execution plan strategy is not a registered StrategyId.",
            code="PLAN_STRATEGY_INVALID",
        )
    if strategy_id not in registry:
        raise PolicyError(
            f"Strategy '{strategy_id.value}' is not registered.",
            code="POLICY_STRATEGY_NOT_REGISTERED",
        )
    return registry[strategy_id]


def _apply_output_mode_policy(
    *,
    plan: ExecutionPlan,
    request: PromptRequest,
    strategy: StrategyDefinition,
    changes: list[str],
) -> OutputContract:
    mode = plan.output_contract.mode
    if not isinstance(mode, OutputMode):
        raise ExecutionPlanValidationError(
            "Execution plan output mode is invalid.",
            code="PLAN_OUTPUT_MODE_INVALID",
        )

    if request.requested_output_mode is not None:
        requested_mode = request.requested_output_mode
        if requested_mode not in strategy.supported_output_modes:
            raise PolicyError(
                (
                    f"Strategy '{strategy.strategy_id.value}' does not support "
                    f"caller-requested output mode '{requested_mode.value}'."
                ),
                code="POLICY_OUTPUT_MODE_UNSUPPORTED",
            )
        if mode is not requested_mode:
            changes.append(
                f"output_contract.mode changed from '{mode.value}' "
                f"to caller-requested '{requested_mode.value}'"
            )
            mode = requested_mode
    elif mode not in strategy.supported_output_modes:
        mode = _default_supported_mode(strategy)
        changes.append(
            "output_contract.mode changed to "
            f"'{mode.value}' because strategy '{strategy.strategy_id.value}' "
            "does not support the model-selected mode"
        )

    return OutputContract(
        mode=mode,
        structure=plan.output_contract.structure,
        tone=plan.output_contract.tone,
        length=plan.output_contract.length,
        audience=plan.output_contract.audience,
    )


def _apply_clarification_policy(
    clarification: ClarificationDecision,
    changes: list[str],
) -> ClarificationDecision:
    action = clarification.action
    if not isinstance(action, ClarificationAction):
        raise ExecutionPlanValidationError(
            "Execution plan clarification action is invalid.",
            code="PLAN_CLARIFICATION_INVALID",
        )

    if action is not ClarificationAction.ASK_CLARIFICATION:
        return clarification

    question = " ".join((clarification.question or "").split())
    if question == "":
        raise PolicyError(
            "Clarification outcome requires one focused question.",
            code="POLICY_CLARIFICATION_QUESTION_REQUIRED",
        )
    if question.count("?") > 1:
        raise PolicyError(
            "Clarification outcome may contain only one focused question.",
            code="POLICY_CLARIFICATION_TOO_MANY_QUESTIONS",
        )
    if question != clarification.question:
        changes.append("clarification.question whitespace normalized")
    return ClarificationDecision(
        action=action,
        question=question,
        reason=clarification.reason,
    )


def _apply_critic_policy(
    *,
    plan: ExecutionPlan,
    strategy: StrategyDefinition,
    config: PromptOrchestratorConfig,
    changes: list[str],
) -> bool:
    required = _critic_required_by_policy(plan, strategy, config)
    if required and not plan.critic_required:
        changes.append("critic_required changed from false to true by policy")
        return True
    if not required and plan.critic_required and not config.runtime.enable_critic:
        changes.append("critic_required changed from true to false by runtime policy")
        return False
    return plan.critic_required


def _critic_required_by_policy(
    plan: ExecutionPlan,
    strategy: StrategyDefinition,
    config: PromptOrchestratorConfig,
) -> bool:
    if plan.understanding.risk_level is RiskLevel.HIGH:
        return True
    if plan.understanding.complexity is TaskComplexity.HIGH_STAKES:
        return True
    if strategy.requires_caution:
        return True

    override = config.runtime.strategy_overrides.get(strategy.strategy_id)
    if override is not None and override.enable_critic is not None:
        return override.enable_critic
    return config.runtime.enable_critic and strategy.critic_recommended


def _normalize_string_list(
    values: list[str],
    *,
    field_name: str,
    changes: list[str],
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value).split())
        if cleaned == "":
            continue
        marker = cleaned.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        normalized.append(cleaned)
        if len(normalized) == MAX_LIST_ITEMS:
            break

    if normalized != values:
        changes.append(f"{field_name} normalized and deduplicated")
    return normalized


def _normalize_understanding(
    understanding: TaskUnderstanding,
    changes: list[str],
) -> TaskUnderstanding:
    risk_categories = _normalize_string_list(
        understanding.risk_categories,
        field_name="understanding.risk_categories",
        changes=changes,
    )
    missing_information = _normalize_string_list(
        understanding.missing_information,
        field_name="understanding.missing_information",
        changes=changes,
    )
    assumptions = _normalize_string_list(
        understanding.assumptions,
        field_name="understanding.assumptions",
        changes=changes,
    )
    uncertainties = _normalize_string_list(
        understanding.uncertainties,
        field_name="understanding.uncertainties",
        changes=changes,
    )
    return TaskUnderstanding(
        user_goal=understanding.user_goal,
        intent=understanding.intent,
        task_type=understanding.task_type,
        complexity=understanding.complexity,
        ambiguity=understanding.ambiguity,
        risk_level=understanding.risk_level,
        risk_categories=risk_categories,
        missing_information=missing_information,
        assumptions=assumptions,
        uncertainties=uncertainties,
        concise_rationale=understanding.concise_rationale,
    )


def _default_supported_mode(strategy: StrategyDefinition) -> OutputMode:
    if OutputMode.TEXT in strategy.supported_output_modes:
        return OutputMode.TEXT
    return sorted(strategy.supported_output_modes, key=lambda item: item.value)[0]


def _outcome_for(action: ClarificationAction) -> PolicyOutcome:
    if action is ClarificationAction.PROCEED:
        return PolicyOutcome.PROCEED
    if action is ClarificationAction.ASK_CLARIFICATION:
        return PolicyOutcome.CLARIFICATION_REQUIRED
    return PolicyOutcome.REFUSED
