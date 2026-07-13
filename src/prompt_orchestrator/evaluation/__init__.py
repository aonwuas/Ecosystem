"""Evaluation harness: prove and track the orchestration thesis.

This package compares full orchestration (the treatment) against control arms —
including equal-compute best-of-N and self-refine — with explicit token/latency
cost accounting, deterministic checks, paired significance tests, and an optional
pairwise model judge.
"""

from prompt_orchestrator.evaluation.arms import (
    CONTROL_KINDS,
    TREATMENT_NAME,
    Arm,
    ArmSpec,
    build_arms,
)
from prompt_orchestrator.evaluation.checks import CheckOutcome, evaluate_checks
from prompt_orchestrator.evaluation.corpus import (
    EvalCase,
    EvalChecks,
    EvalCorpus,
    load_corpus,
)
from prompt_orchestrator.evaluation.harness import run_evaluation
from prompt_orchestrator.evaluation.judge import JudgeVerdict, judge_pair
from prompt_orchestrator.evaluation.report import (
    ArmAggregate,
    ArmResult,
    CaseResult,
    ComparisonAggregate,
    EvalReport,
    render_report_text,
)

__all__ = [
    "CONTROL_KINDS",
    "TREATMENT_NAME",
    "Arm",
    "ArmAggregate",
    "ArmResult",
    "ArmSpec",
    "CaseResult",
    "CheckOutcome",
    "ComparisonAggregate",
    "EvalCase",
    "EvalChecks",
    "EvalCorpus",
    "EvalReport",
    "JudgeVerdict",
    "build_arms",
    "evaluate_checks",
    "judge_pair",
    "load_corpus",
    "render_report_text",
    "run_evaluation",
]
