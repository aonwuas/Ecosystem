"""One-pass revision stage."""

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
    ValidatedExecutionPlan,
)
from prompt_orchestrator.domain.enums import ModelRole
from prompt_orchestrator.exceptions import ProviderError, RevisionError
from prompt_orchestrator.prompts import (
    REVISION_VARIABLES,
    load_template,
    render_template,
)


@dataclass(frozen=True)
class RevisionStageResult:
    """Revision-stage output."""

    draft: DraftResponse
    revision_performed: bool
    warnings: list[str]


def run_revision_stage(
    *,
    intake: IntakeResult,
    validated_plan: ValidatedExecutionPlan,
    draft: DraftResponse,
    critic_result: CriticResult,
    config: PromptOrchestratorConfig,
    client: ModelClient,
) -> RevisionStageResult:
    """Run at most one revision and preserve the original draft on failure."""
    if not config.runtime.enable_revision or config.runtime.max_revision_attempts == 0:
        return RevisionStageResult(
            draft=draft,
            revision_performed=False,
            warnings=["revision skipped by runtime policy"],
        )
    if not critic_result.revision_recommended:
        return RevisionStageResult(draft=draft, revision_performed=False, warnings=[])

    try:
        revised = _call_revision(
            intake=intake,
            validated_plan=validated_plan,
            draft=draft,
            critic_result=critic_result,
            config=config,
            client=client,
        )
    except (ProviderError, RevisionError) as error:
        return RevisionStageResult(
            draft=draft,
            revision_performed=False,
            warnings=[f"revision failed; original draft preserved: {error}"],
        )

    return RevisionStageResult(draft=revised, revision_performed=True, warnings=[])


def _call_revision(
    *,
    intake: IntakeResult,
    validated_plan: ValidatedExecutionPlan,
    draft: DraftResponse,
    critic_result: CriticResult,
    config: PromptOrchestratorConfig,
    client: ModelClient,
) -> DraftResponse:
    resolved = config.resolve_role(ModelRole.REVISION)
    response = client.generate(
        ModelRequest(
            role=ModelRole.REVISION,
            model_name=resolved.model_name,
            messages=[
                ModelMessage(
                    role="system",
                    content=(
                        "You are Prompt Orchestrator's revision stage. "
                        "Return the complete revised answer only."
                    ),
                ),
                ModelMessage(
                    role="user",
                    content=_render_revision_prompt(
                        intake=intake,
                        validated_plan=validated_plan,
                        draft=draft,
                        critic_result=critic_result,
                    ),
                ),
            ],
            temperature=resolved.model.temperature,
            max_output_tokens=resolved.model.max_output_tokens,
            timeout_seconds=resolved.model.timeout_seconds,
            request_kind="revision",
        )
    )
    text = response.text.strip()
    if text == "":
        raise RevisionError(
            "Revision returned an empty response.",
            code="REVISION_EMPTY_RESPONSE",
        )
    return DraftResponse(
        text=text,
        model_name=resolved.model_name,
        role=ModelRole.REVISION,
        usage=response.usage,
    )


def _render_revision_prompt(
    *,
    intake: IntakeResult,
    validated_plan: ValidatedExecutionPlan,
    draft: DraftResponse,
    critic_result: CriticResult,
) -> str:
    return render_template(
        load_template("revision.md"),
        {
            "original_request": intake.normalized_prompt,
            "caller_context": intake.normalized_context or "",
            "execution_plan": validated_plan.plan.model_dump_json(),
            "draft": draft.text,
            "critic_issues": _format_critic_issues(critic_result),
            "revision_instruction": critic_result.revision_instruction or "",
        },
        allowed_variables=REVISION_VARIABLES,
    )


def _format_critic_issues(critic_result: CriticResult) -> str:
    if not critic_result.issues:
        return "- none"
    return "\n".join(
        f"- {issue.severity.value}: {issue.message}" for issue in critic_result.issues
    )
