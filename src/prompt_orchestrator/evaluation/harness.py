"""Evaluation harness comparing orchestrated output against a single call.

For each case the harness runs the full orchestration pipeline and, by default,
a single-call baseline through the same worker model, metering the token and
latency cost of each arm. Deterministic checks always run; the model judge runs
only when enabled. The result is an :class:`EvalReport`.
"""

from __future__ import annotations

from prompt_orchestrator.clients import MeteringModelClient, ModelClient
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import FinalResponse, PromptRequest, RunUsage
from prompt_orchestrator.domain.enums import PipelineStatus
from prompt_orchestrator.evaluation.checks import evaluate_checks
from prompt_orchestrator.evaluation.corpus import EvalCase, EvalCorpus
from prompt_orchestrator.evaluation.judge import JudgeError, judge_pair
from prompt_orchestrator.evaluation.report import ArmResult, CaseResult, EvalReport
from prompt_orchestrator.pipeline import PipelineRunner

_PREVIEW_LIMIT = 300


def run_evaluation(
    *,
    corpus: EvalCorpus,
    config: PromptOrchestratorConfig,
    client: ModelClient,
    compare_baseline: bool = True,
    judge: bool = False,
) -> EvalReport:
    """Evaluate every case in the corpus and return an aggregated report.

    The supplied ``client`` is wrapped in a :class:`MeteringModelClient` so cost
    is captured per arm. Client lifecycle (closing) remains the caller's
    responsibility.
    """
    metering = MeteringModelClient(client, config=config)
    runner = PipelineRunner(config=config, client=metering)

    results: list[CaseResult] = []
    for index, case in enumerate(corpus.cases):
        results.append(
            _evaluate_case(
                case=case,
                case_index=index,
                config=config,
                metering=metering,
                runner=runner,
                compare_baseline=compare_baseline,
                judge=judge,
            )
        )
    return EvalReport.from_cases(results)


def _evaluate_case(
    *,
    case: EvalCase,
    case_index: int,
    config: PromptOrchestratorConfig,
    metering: MeteringModelClient,
    runner: PipelineRunner,
    compare_baseline: bool,
    judge: bool,
) -> CaseResult:
    request = PromptRequest(prompt=case.prompt, context=case.context)

    metering.reset()
    orchestrated = runner.run(request).final_response
    orchestrated_usage = metering.snapshot()
    orchestrated_arm = _arm_result(
        arm="orchestrated",
        response=orchestrated,
        usage=orchestrated_usage,
        case=case,
    )

    baseline_arm: ArmResult | None = None
    baseline: FinalResponse | None = None
    if compare_baseline:
        metering.reset()
        baseline = runner.run_baseline(request)
        baseline_usage = metering.snapshot()
        baseline_arm = _arm_result(
            arm="baseline",
            response=baseline,
            usage=baseline_usage,
            case=case,
        )

    verdict = None
    judge_error: str | None = None
    if judge and baseline is not None and _both_completed(orchestrated, baseline):
        try:
            verdict = judge_pair(
                case=case,
                case_index=case_index,
                orchestrated=orchestrated,
                baseline=baseline,
                config=config,
                client=metering,
            )
        except JudgeError as error:
            judge_error = _truncate(f"{getattr(error, 'code', 'JUDGE_ERROR')}: {error}")
    elif judge and baseline is not None:
        judge_error = "skipped: an arm did not complete"

    return CaseResult(
        case_id=case.id,
        category=case.category,
        orchestrated=orchestrated_arm,
        baseline=baseline_arm,
        judge=verdict,
        judge_error=judge_error,
    )


def _arm_result(
    *,
    arm: str,
    response: FinalResponse,
    usage: RunUsage,
    case: EvalCase,
) -> ArmResult:
    return ArmResult(
        arm=arm,
        status=response.status,
        checks=evaluate_checks(response, case.checks),
        usage=usage,
        answer_preview=_preview(response),
    )


def _both_completed(orchestrated: FinalResponse, baseline: FinalResponse) -> bool:
    completed = {PipelineStatus.COMPLETED, PipelineStatus.COMPLETED_WITH_WARNINGS}
    return orchestrated.status in completed and baseline.status in completed


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
