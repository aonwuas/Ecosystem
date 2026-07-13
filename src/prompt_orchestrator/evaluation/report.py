"""Evaluation report models and text rendering.

The report answers the thesis question at the fleet level: for each arm it shows
the deterministic pass rate with a confidence interval and the token/latency
cost; for each control it shows how the treatment compares (paired significance
on pass/fail, judge win-rate with an interval) and the achieved compute ratio, so
"is orchestration worth its cost?" can be read off directly and fairly.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import Field

from prompt_orchestrator.domain import RunUsage
from prompt_orchestrator.domain._base import DomainModel, ShortText
from prompt_orchestrator.domain.enums import PipelineStatus
from prompt_orchestrator.evaluation.checks import CheckOutcome
from prompt_orchestrator.evaluation.judge import JudgeVerdict
from prompt_orchestrator.evaluation.stats import (
    mcnemar_p_value,
    sign_test_p_value,
    wilson_interval,
)

MAX_ARMS = 16
MAX_CASES = 500


class ArmResult(DomainModel):
    """Outcome and cost of one arm for one case."""

    arm: ShortText
    kind: ShortText
    status: PipelineStatus
    checks: CheckOutcome
    usage: RunUsage
    answer_preview: str = Field(default="", max_length=500)


class CaseResult(DomainModel):
    """Per-case results across all arms plus optional judge verdicts."""

    case_id: ShortText
    category: ShortText | None = None
    arms: dict[str, ArmResult] = Field(default_factory=dict, max_length=MAX_ARMS)
    judgements: dict[str, JudgeVerdict] = Field(
        default_factory=dict, max_length=MAX_ARMS
    )
    judge_errors: dict[str, ShortText] = Field(
        default_factory=dict, max_length=MAX_ARMS
    )


class ArmAggregate(DomainModel):
    """Aggregated pass rate and cost for one arm across all cases."""

    arm: ShortText
    kind: ShortText
    cases: int = Field(ge=0, strict=True)
    passes: int = Field(ge=0, strict=True)
    pass_rate: float = Field(ge=0.0, le=1.0)
    pass_rate_low: float = Field(ge=0.0, le=1.0)
    pass_rate_high: float = Field(ge=0.0, le=1.0)
    total_tokens: int | None = Field(default=None, ge=0, strict=True)
    total_ms: float = Field(default=0.0, ge=0.0)
    calls: int = Field(default=0, ge=0, strict=True)
    compute_ratio_vs_treatment: float | None = Field(default=None, ge=0.0)
    quality_per_1k_tokens: float | None = Field(default=None, ge=0.0)


class ComparisonAggregate(DomainModel):
    """Treatment vs one control: paired significance and judge win-rate."""

    control: ShortText
    # Paired deterministic pass/fail (McNemar on discordant pairs).
    treatment_only_passes: int = Field(ge=0, strict=True)
    control_only_passes: int = Field(ge=0, strict=True)
    mcnemar_p: float = Field(ge=0.0, le=1.0)
    # Judge outcomes (present only when judging ran).
    judge_treatment_wins: int = Field(default=0, ge=0, strict=True)
    judge_control_wins: int = Field(default=0, ge=0, strict=True)
    judge_ties: int = Field(default=0, ge=0, strict=True)
    judge_errors: int = Field(default=0, ge=0, strict=True)
    judge_sign_p: float | None = Field(default=None, ge=0.0, le=1.0)
    judge_win_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    judge_win_rate_low: float | None = Field(default=None, ge=0.0, le=1.0)
    judge_win_rate_high: float | None = Field(default=None, ge=0.0, le=1.0)


class EvalReport(DomainModel):
    """Aggregated evaluation across all cases and arms."""

    case_count: int = Field(ge=0, strict=True)
    treatment: ShortText
    arm_names: list[ShortText] = Field(default_factory=list, max_length=MAX_ARMS)
    arms: dict[str, ArmAggregate] = Field(default_factory=dict, max_length=MAX_ARMS)
    comparisons: dict[str, ComparisonAggregate] = Field(
        default_factory=dict, max_length=MAX_ARMS
    )
    cases: list[CaseResult] = Field(default_factory=list, max_length=MAX_CASES)

    @classmethod
    def from_cases(cls, cases: list[CaseResult], *, treatment: str) -> EvalReport:
        arm_names = list(cases[0].arms) if cases else [treatment]
        treatment_tokens = _arm_total_tokens(cases, treatment)
        arms = {
            name: _aggregate_arm(
                cases,
                name,
                treatment_tokens=None if name == treatment else treatment_tokens,
            )
            for name in arm_names
        }
        comparisons = {
            name: _compare(cases, treatment=treatment, control=name)
            for name in arm_names
            if name != treatment
        }
        return cls(
            case_count=len(cases),
            treatment=treatment,
            arm_names=arm_names,
            arms=arms,
            comparisons=comparisons,
            cases=cases,
        )


def _aggregate_arm(
    cases: list[CaseResult], name: str, treatment_tokens: int | None
) -> ArmAggregate:
    results = [case.arms[name] for case in cases if name in case.arms]
    passes = sum(1 for result in results if result.checks.passed)
    total_tokens = _sum_tokens(result.usage for result in results)
    interval = wilson_interval(passes, len(results))
    compute_ratio = (
        total_tokens / treatment_tokens
        if total_tokens is not None and treatment_tokens
        else None
    )
    quality_per_1k = (
        passes / (total_tokens / 1000)
        if total_tokens is not None and total_tokens > 0
        else None
    )
    kind = results[0].kind if results else "unknown"
    return ArmAggregate(
        arm=name,
        kind=kind,
        cases=len(results),
        passes=passes,
        pass_rate=interval.point,
        pass_rate_low=interval.low,
        pass_rate_high=interval.high,
        total_tokens=total_tokens,
        total_ms=sum(result.usage.total_duration_ms for result in results),
        calls=sum(result.usage.call_count for result in results),
        compute_ratio_vs_treatment=compute_ratio,
        quality_per_1k_tokens=quality_per_1k,
    )


def _compare(
    cases: list[CaseResult], *, treatment: str, control: str
) -> ComparisonAggregate:
    treatment_only = 0
    control_only = 0
    for case in cases:
        if treatment not in case.arms or control not in case.arms:
            continue
        t_pass = case.arms[treatment].checks.passed
        c_pass = case.arms[control].checks.passed
        if t_pass and not c_pass:
            treatment_only += 1
        elif c_pass and not t_pass:
            control_only += 1

    verdicts = [
        case.judgements[control] for case in cases if control in case.judgements
    ]
    treatment_wins = sum(1 for v in verdicts if v.winner == "treatment")
    control_wins = sum(1 for v in verdicts if v.winner == "control")
    ties = sum(1 for v in verdicts if v.winner == "tie")
    judge_errors = sum(1 for case in cases if control in case.judge_errors)

    decisive = treatment_wins + control_wins
    sign_p: float | None = None
    win_rate: float | None = None
    win_low: float | None = None
    win_high: float | None = None
    if verdicts:
        sign_p = sign_test_p_value(treatment_wins, control_wins)
        if decisive > 0:
            interval = wilson_interval(treatment_wins, decisive)
            win_rate, win_low, win_high = (
                interval.point,
                interval.low,
                interval.high,
            )

    return ComparisonAggregate(
        control=control,
        treatment_only_passes=treatment_only,
        control_only_passes=control_only,
        mcnemar_p=mcnemar_p_value(treatment_only, control_only),
        judge_treatment_wins=treatment_wins,
        judge_control_wins=control_wins,
        judge_ties=ties,
        judge_errors=judge_errors,
        judge_sign_p=sign_p,
        judge_win_rate=win_rate,
        judge_win_rate_low=win_low,
        judge_win_rate_high=win_high,
    )


def _arm_total_tokens(cases: list[CaseResult], name: str) -> int | None:
    return _sum_tokens(case.arms[name].usage for case in cases if name in case.arms)


def _sum_tokens(usages: Iterable[RunUsage]) -> int | None:
    total: int | None = None
    for usage in usages:
        if usage.total_tokens is None:
            continue
        total = usage.total_tokens if total is None else total + usage.total_tokens
    return total


def render_report_text(report: EvalReport) -> str:
    """Render a compact human-readable evaluation summary."""
    lines: list[str] = [
        "Evaluation report",
        f"Cases: {report.case_count}   Treatment: {report.treatment}",
        "",
        "Arms (pass rate 95% CI | cost | fairness):",
    ]
    for name in report.arm_names:
        lines.append(_arm_line(report.arms[name]))

    if report.comparisons:
        lines.append("")
        lines.append("Treatment vs controls:")
        for name, comparison in report.comparisons.items():
            lines.extend(_comparison_lines(report.treatment, name, comparison))

    lines.append("")
    lines.append("Per case:")
    for case in report.cases:
        lines.append(f"- {case.case_id} [{case.category or 'uncategorized'}]")
        for name in report.arm_names:
            if name in case.arms:
                lines.append(f"    {name}: {_case_arm_line(case.arms[name])}")
        for control, verdict in case.judgements.items():
            consistent = "" if verdict.order_consistent else " (order-dependent)"
            lines.append(
                f"    judge vs {control}: {verdict.winner}{consistent} "
                f"(confidence {verdict.confidence})"
            )
    return "\n".join(lines)


def _arm_line(arm: ArmAggregate) -> str:
    tokens = _fmt_tokens(arm.total_tokens)
    ratio = (
        "treatment"
        if arm.compute_ratio_vs_treatment is None
        else f"{arm.compute_ratio_vs_treatment:.2f}x tokens"
    )
    quality = (
        "?"
        if arm.quality_per_1k_tokens is None
        else f"{arm.quality_per_1k_tokens:.2f} pass/1k"
    )
    return (
        f"  {arm.arm}: {arm.passes}/{arm.cases} pass "
        f"[{arm.pass_rate_low:.2f}, {arm.pass_rate_high:.2f}] | "
        f"{arm.calls} calls, {tokens} tokens, {arm.total_ms:.0f} ms | "
        f"{ratio}, {quality}"
    )


def _comparison_lines(
    treatment: str, control: str, comparison: ComparisonAggregate
) -> list[str]:
    lines = [
        f"  {treatment} vs {control}:",
        (
            f"    checks: {treatment} +{comparison.treatment_only_passes} / "
            f"{control} +{comparison.control_only_passes} "
            f"(McNemar p={comparison.mcnemar_p:.3f})"
        ),
    ]
    if comparison.judge_win_rate is not None:
        lines.append(
            f"    judge: {comparison.judge_treatment_wins}W-"
            f"{comparison.judge_control_wins}L-{comparison.judge_ties}T, "
            f"win-rate {comparison.judge_win_rate:.2f} "
            f"[{comparison.judge_win_rate_low:.2f}, "
            f"{comparison.judge_win_rate_high:.2f}], "
            f"sign p={_fmt_p(comparison.judge_sign_p)}"
        )
    elif (
        comparison.judge_treatment_wins
        + comparison.judge_control_wins
        + (comparison.judge_ties)
        > 0
    ):
        lines.append(
            f"    judge: {comparison.judge_treatment_wins}W-"
            f"{comparison.judge_control_wins}L-{comparison.judge_ties}T"
        )
    return lines


def _case_arm_line(arm: ArmResult) -> str:
    verdict = "PASS" if arm.checks.passed else "FAIL"
    detail = "" if arm.checks.passed else f" [{'; '.join(arm.checks.failures)}]"
    return (
        f"{verdict} {arm.status.value}, "
        f"{_fmt_tokens(arm.usage.total_tokens)} tokens{detail}"
    )


def _fmt_tokens(value: int | None) -> str:
    return "?" if value is None else str(value)


def _fmt_p(value: float | None) -> str:
    return "?" if value is None else f"{value:.3f}"
