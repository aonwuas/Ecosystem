"""Critic review stage with one structured-output repair attempt."""

from __future__ import annotations

from dataclasses import dataclass

from prompt_orchestrator.clients import ModelClient
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import (
    CriticResult,
    DraftResponse,
    IntakeResult,
    ModelMessage,
    ModelRequest,
    QualityResult,
    ValidatedExecutionPlan,
)
from prompt_orchestrator.domain.enums import CriticStatus, ModelRole
from prompt_orchestrator.exceptions import (
    CriticError,
    ProviderError,
    StructuredOutputError,
)
from prompt_orchestrator.parsing import (
    RepairBudget,
    build_repair_request_data,
    validate_structured_output,
)
from prompt_orchestrator.prompts import CRITIC_VARIABLES, load_template, render_template


@dataclass(frozen=True)
class CriticStageResult:
    """Critic-stage output."""

    quality: QualityResult
    critic_result: CriticResult | None = None


def run_critic_stage(
    *,
    intake: IntakeResult,
    validated_plan: ValidatedExecutionPlan,
    draft: DraftResponse,
    config: PromptOrchestratorConfig,
    client: ModelClient,
) -> CriticStageResult:
    """Evaluate a worker draft or degrade according to critic policy."""
    if not config.runtime.enable_critic or not validated_plan.plan.critic_required:
        return CriticStageResult(
            quality=QualityResult(
                status=CriticStatus.SKIPPED,
                warnings=["critic review skipped by runtime policy"],
            )
        )

    try:
        critic = _call_and_parse_critic(
            intake=intake,
            validated_plan=validated_plan,
            draft=draft,
            config=config,
            client=client,
            repair_error=None,
        )
    except (ProviderError, StructuredOutputError) as first_error:
        if isinstance(first_error, StructuredOutputError):
            budget = RepairBudget(
                max_attempts=config.runtime.structured_output_repair_attempts
            )
            if budget.can_repair():
                try:
                    critic = _call_and_parse_critic(
                        intake=intake,
                        validated_plan=validated_plan,
                        draft=draft,
                        config=config,
                        client=client,
                        repair_error=first_error,
                    )
                except (ProviderError, StructuredOutputError) as repair_error:
                    return _handle_critic_failure(config=config, error=repair_error)
                return _quality_from_critic(critic)

        return _handle_critic_failure(config=config, error=first_error)

    return _quality_from_critic(critic)


def _call_and_parse_critic(
    *,
    intake: IntakeResult,
    validated_plan: ValidatedExecutionPlan,
    draft: DraftResponse,
    config: PromptOrchestratorConfig,
    client: ModelClient,
    repair_error: StructuredOutputError | None,
) -> CriticResult:
    resolved = config.resolve_role(ModelRole.CRITIC)
    prompt = (
        _render_repair_prompt(error=repair_error)
        if repair_error is not None
        else _render_critic_prompt(
            intake=intake,
            validated_plan=validated_plan,
            draft=draft,
        )
    )
    response = client.generate(
        ModelRequest(
            role=ModelRole.CRITIC,
            model_name=resolved.model_name,
            messages=[
                ModelMessage(
                    role="system",
                    content=(
                        "You are Prompt Orchestrator's critic stage. "
                        "Return structured JSON only."
                    ),
                ),
                ModelMessage(role="user", content=prompt),
            ],
            temperature=resolved.model.temperature,
            max_output_tokens=resolved.model.max_output_tokens,
            timeout_seconds=resolved.model.timeout_seconds,
            request_kind="critic",
        )
    )
    try:
        return validate_structured_output(response.text, CriticResult).value
    except StructuredOutputError as exc:
        object.__setattr__(exc, "invalid_response", response.text)
        raise


def _render_critic_prompt(
    *,
    intake: IntakeResult,
    validated_plan: ValidatedExecutionPlan,
    draft: DraftResponse,
) -> str:
    return render_template(
        load_template("critic.md"),
        {
            "original_request": intake.normalized_prompt,
            "caller_context": intake.normalized_context or "",
            "execution_plan": validated_plan.plan.model_dump_json(),
            "draft": draft.text,
            "quality_criteria": _format_list(validated_plan.plan.quality_criteria),
        },
        allowed_variables=CRITIC_VARIABLES,
    )


def _render_repair_prompt(*, error: StructuredOutputError | None) -> str:
    assert error is not None
    repair = build_repair_request_data(
        invalid_response=str(getattr(error, "invalid_response", "")),
        error=error,
        model_type=CriticResult,
    )
    return (
        "Repair the previous critic output. "
        "Return a corrected JSON object only.\n\n"
        f"Validation errors:\n{'; '.join(repair.validation_errors)}\n\n"
        f"<INVALID_RESPONSE>\n{repair.invalid_response}\n</INVALID_RESPONSE>\n\n"
        f"Required JSON shape:\n{repair.required_json_shape}"
    )


def _quality_from_critic(critic: CriticResult) -> CriticStageResult:
    status = (
        CriticStatus.PASSED
        if critic.passes
        else CriticStatus.REVISION_RECOMMENDED
        if critic.revision_recommended
        else CriticStatus.FAILED
    )
    return CriticStageResult(
        quality=QualityResult(status=status, critic_result=critic),
        critic_result=critic,
    )


def _handle_critic_failure(
    *,
    config: PromptOrchestratorConfig,
    error: ProviderError | StructuredOutputError,
) -> CriticStageResult:
    if config.runtime.strict_critic:
        raise CriticError(
            f"Critic review failed: {error}",
            code="CRITIC_FAILED",
        ) from error
    return CriticStageResult(
        quality=QualityResult(
            status=CriticStatus.NOT_CHECKED,
            warnings=["critic review failed; draft was not checked"],
        )
    )


def _format_list(values: list[str]) -> str:
    if not values:
        return "- none"
    return "\n".join(f"- {value}" for value in values)
