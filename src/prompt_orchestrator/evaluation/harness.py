"""Evaluation harness comparing a treatment against control arms.

For each case the harness runs every arm (full orchestration = treatment; the
controls it must beat, including equal-compute best-of-N and self-refine),
metering the token and latency cost of each arm separately. Deterministic checks
always run; the pairwise model judge runs only when enabled, comparing the
treatment against each completed control. The result is an :class:`EvalReport`.
"""

from __future__ import annotations

from prompt_orchestrator.clients import MeteringModelClient, ModelClient
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import FinalResponse, PromptRequest, RunUsage
from prompt_orchestrator.domain.enums import PipelineStatus
from prompt_orchestrator.evaluation.arms import Arm, ArmSpec, build_arms
from prompt_orchestrator.evaluation.checks import evaluate_checks
from prompt_orchestrator.evaluation.corpus import EvalCase, EvalCorpus
from prompt_orchestrator.evaluation.judge import JudgeError, JudgeVerdict, judge_pair
from prompt_orchestrator.evaluation.report import ArmResult, CaseResult, EvalReport
from prompt_orchestrator.pipeline import PipelineRunner

_PREVIEW_LIMIT = 300
_COMPLETED = {PipelineStatus.COMPLETED, PipelineStatus.COMPLETED_WITH_WARNINGS}


def run_evaluation(
    *,
    corpus: EvalCorpus,
    config: PromptOrchestratorConfig,
    client: ModelClient,
    arm_spec: ArmSpec | None = None,
    judge: bool = False,
) -> EvalReport:
    """Evaluate every case across all arms and return an aggregated report.

    The supplied ``client`` is wrapped in a :class:`MeteringModelClient` so cost
    is captured per arm; the meter is reset between arms so each arm's cost is
    isolated. Client lifecycle (closing) remains the caller's responsibility.
    """
    spec = (arm_spec or ArmSpec()).validated()
    metering = MeteringModelClient(client, config=config)
    runner = PipelineRunner(config=config, client=metering)
    arms = build_arms(runner, spec)
    treatment = next(arm for arm in arms if arm.is_treatment)
    controls = [arm for arm in arms if not arm.is_treatment]

    results = [
        _evaluate_case(
            case=case,
            arms=arms,
            treatment=treatment,
            controls=controls,
            config=config,
            metering=metering,
            judge=judge,
        )
        for case in corpus.cases
    ]
    return EvalReport.from_cases(results, treatment=treatment.name)


def _evaluate_case(
    *,
    case: EvalCase,
    arms: list[Arm],
    treatment: Arm,
    controls: list[Arm],
    config: PromptOrchestratorConfig,
    metering: MeteringModelClient,
    judge: bool,
) -> CaseResult:
    request = PromptRequest(prompt=case.prompt, context=case.context)

    responses: dict[str, FinalResponse] = {}
    arm_results: dict[str, ArmResult] = {}
    for arm in arms:
        metering.reset()
        response = arm.run(request)
        responses[arm.name] = response
        arm_results[arm.name] = _arm_result(
            arm=arm, response=response, usage=metering.snapshot(), case=case
        )

    judgements: dict[str, JudgeVerdict] = {}
    judge_errors: dict[str, str] = {}
    if judge:
        _judge_controls(
            case=case,
            treatment_response=responses[treatment.name],
            controls=controls,
            responses=responses,
            config=config,
            metering=metering,
            judgements=judgements,
            judge_errors=judge_errors,
        )

    return CaseResult(
        case_id=case.id,
        category=case.category,
        arms=arm_results,
        judgements=judgements,
        judge_errors=judge_errors,
    )


def _judge_controls(
    *,
    case: EvalCase,
    treatment_response: FinalResponse,
    controls: list[Arm],
    responses: dict[str, FinalResponse],
    config: PromptOrchestratorConfig,
    metering: MeteringModelClient,
    judgements: dict[str, JudgeVerdict],
    judge_errors: dict[str, str],
) -> None:
    treatment_ok = treatment_response.status in _COMPLETED
    for control in controls:
        control_response = responses[control.name]
        if not (treatment_ok and control_response.status in _COMPLETED):
            judge_errors[control.name] = "skipped: an arm did not complete"
            continue
        try:
            judgements[control.name] = judge_pair(
                case=case,
                treatment=treatment_response,
                control=control_response,
                config=config,
                client=metering,
            )
        except JudgeError as error:
            judge_errors[control.name] = _truncate(
                f"{getattr(error, 'code', 'JUDGE_ERROR')}: {error}"
            )


def _arm_result(
    *,
    arm: Arm,
    response: FinalResponse,
    usage: RunUsage,
    case: EvalCase,
) -> ArmResult:
    return ArmResult(
        arm=arm.name,
        kind=arm.kind,
        status=response.status,
        checks=evaluate_checks(response, case.checks),
        usage=usage,
        answer_preview=_preview(response),
    )


def _preview(response: FinalResponse) -> str:
    text = (
        response.clarification_question or ""
        if response.status is PipelineStatus.CLARIFICATION_REQUIRED
        else response.text
    )
    collapsed = " ".join(text.split())
    if len(collapsed) <= _PREVIEW_LIMIT:
        return collapsed
    return f"{collapsed[: _PREVIEW_LIMIT - 3]}..."


def _truncate(value: str) -> str:
    return value if len(value) <= 500 else f"{value[:497]}..."
