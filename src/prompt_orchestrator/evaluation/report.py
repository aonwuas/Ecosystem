"""Evaluation report models and text rendering.

The report is the artifact that answers the thesis question: it puts each arm's
deterministic pass rate, optional judge verdicts, and token/latency cost side by
side so the quality lift of orchestration can be weighed against its cost.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import Field

from prompt_orchestrator.domain import RunUsage
from prompt_orchestrator.domain._base import DomainModel, ShortText
from prompt_orchestrator.domain.enums import PipelineStatus
from prompt_orchestrator.evaluation.checks import CheckOutcome
from prompt_orchestrator.evaluation.judge import JudgeVerdict

ArmName = ShortText


class ArmResult(DomainModel):
    """Outcome and cost of one arm (orchestrated or baseline) for one case."""

    arm: ArmName
    status: PipelineStatus
    checks: CheckOutcome
    usage: RunUsage
    answer_preview: str = Field(default="", max_length=500)


class CaseResult(DomainModel):
    """Per-case results across arms plus an optional judge verdict."""

    case_id: ShortText
    category: ShortText | None = None
    orchestrated: ArmResult
    baseline: ArmResult | None = None
    judge: JudgeVerdict | None = None
    judge_error: ShortText | None = None


class EvalReport(DomainModel):
    """Aggregated evaluation across all cases."""

    case_count: int = Field(ge=0, strict=True)
    orchestrated_passes: int = Field(ge=0, strict=True)
    baseline_passes: int | None = Field(default=None, ge=0, strict=True)
    judge_orchestrated_wins: int = Field(default=0, ge=0, strict=True)
    judge_baseline_wins: int = Field(default=0, ge=0, strict=True)
    judge_ties: int = Field(default=0, ge=0, strict=True)
    judge_errors: int = Field(default=0, ge=0, strict=True)
    orchestrated_total_tokens: int | None = Field(default=None, ge=0, strict=True)
    baseline_total_tokens: int | None = Field(default=None, ge=0, strict=True)
    orchestrated_total_ms: float = Field(default=0.0, ge=0.0)
    baseline_total_ms: float = Field(default=0.0, ge=0.0)
    orchestrated_calls: int = Field(default=0, ge=0, strict=True)
    baseline_calls: int = Field(default=0, ge=0, strict=True)
    cases: list[CaseResult] = Field(default_factory=list, max_length=500)

    @property
    def token_cost_premium(self) -> float | None:
        """Orchestrated tokens per baseline token, when both are known."""
        if self.orchestrated_total_tokens is None or not self.baseline_total_tokens:
            return None
        return self.orchestrated_total_tokens / self.baseline_total_tokens

    @classmethod
    def from_cases(cls, cases: list[CaseResult]) -> EvalReport:
        has_baseline = any(case.baseline is not None for case in cases)
        return cls(
            case_count=len(cases),
            orchestrated_passes=sum(
                1 for case in cases if case.orchestrated.checks.passed
            ),
            baseline_passes=(
                sum(
                    1
                    for case in cases
                    if case.baseline is not None and case.baseline.checks.passed
                )
                if has_baseline
                else None
            ),
            judge_orchestrated_wins=sum(
                1 for case in cases if _judge_winner(case) == "orchestrated"
            ),
            judge_baseline_wins=sum(
                1 for case in cases if _judge_winner(case) == "baseline"
            ),
            judge_ties=sum(1 for case in cases if _judge_winner(case) == "tie"),
            judge_errors=sum(1 for case in cases if case.judge_error is not None),
            orchestrated_total_tokens=_sum_tokens(
                case.orchestrated.usage for case in cases
            ),
            baseline_total_tokens=(
                _sum_tokens(
                    case.baseline.usage for case in cases if case.baseline is not None
                )
                if has_baseline
                else None
            ),
            orchestrated_total_ms=sum(
                case.orchestrated.usage.total_duration_ms for case in cases
            ),
            baseline_total_ms=sum(
                case.baseline.usage.total_duration_ms
                for case in cases
                if case.baseline is not None
            ),
            orchestrated_calls=sum(
                case.orchestrated.usage.call_count for case in cases
            ),
            baseline_calls=sum(
                case.baseline.usage.call_count
                for case in cases
                if case.baseline is not None
            ),
            cases=cases,
        )


def _judge_winner(case: CaseResult) -> str | None:
    return case.judge.winner if case.judge is not None else None


def _sum_tokens(usages: Iterable[RunUsage]) -> int | None:
    total: int | None = None
    for usage in usages:
        if usage.total_tokens is None:
            continue
        total = usage.total_tokens if total is None else total + usage.total_tokens
    return total


def render_report_text(report: EvalReport) -> str:
    """Render a compact human-readable evaluation summary."""
    lines: list[str] = ["Evaluation report", f"Cases: {report.case_count}"]

    lines.append("")
    lines.append("Deterministic checks (passed / total):")
    lines.append(f"  orchestrated: {report.orchestrated_passes}/{report.case_count}")
    if report.baseline_passes is not None:
        lines.append(f"  baseline:     {report.baseline_passes}/{report.case_count}")

    if _judge_used(report):
        lines.append("")
        lines.append("Judge (orchestrated vs baseline):")
        lines.append(f"  orchestrated wins: {report.judge_orchestrated_wins}")
        lines.append(f"  baseline wins:     {report.judge_baseline_wins}")
        lines.append(f"  ties:              {report.judge_ties}")
        if report.judge_errors:
            lines.append(f"  errors:            {report.judge_errors}")

    lines.append("")
    lines.append("Cost:")
    lines.append(
        f"  orchestrated: {report.orchestrated_calls} calls, "
        f"{_fmt_tokens(report.orchestrated_total_tokens)} tokens, "
        f"{report.orchestrated_total_ms:.0f} ms"
    )
    if report.baseline_passes is not None:
        lines.append(
            f"  baseline:     {report.baseline_calls} calls, "
            f"{_fmt_tokens(report.baseline_total_tokens)} tokens, "
            f"{report.baseline_total_ms:.0f} ms"
        )
    premium = report.token_cost_premium
    if premium is not None:
        lines.append(f"  token cost premium: {premium:.2f}x baseline")

    lines.append("")
    lines.append("Per case:")
    for case in report.cases:
        lines.append(f"- {case.case_id} [{case.category or 'uncategorized'}]")
        lines.append(f"    orchestrated: {_arm_line(case.orchestrated)}")
        if case.baseline is not None:
            lines.append(f"    baseline:     {_arm_line(case.baseline)}")
        if case.judge is not None:
            lines.append(
                f"    judge: {case.judge.winner} "
                f"(confidence {case.judge.confidence}): {case.judge.reason}"
            )
        elif case.judge_error is not None:
            lines.append(f"    judge: error ({case.judge_error})")
    return "\n".join(lines)


def _arm_line(arm: ArmResult) -> str:
    verdict = "PASS" if arm.checks.passed else "FAIL"
    detail = "" if arm.checks.passed else f" [{'; '.join(arm.checks.failures)}]"
    return (
        f"{verdict} {arm.status.value}, "
        f"{_fmt_tokens(arm.usage.total_tokens)} tokens{detail}"
    )


def _judge_used(report: EvalReport) -> bool:
    return (
        report.judge_orchestrated_wins
        + report.judge_baseline_wins
        + report.judge_ties
        + report.judge_errors
    ) > 0


def _fmt_tokens(value: int | None) -> str:
    return "?" if value is None else str(value)
