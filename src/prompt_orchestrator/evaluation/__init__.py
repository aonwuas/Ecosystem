"""Evaluation harness: prove and track the orchestration thesis.

This package compares full orchestration against a single-call baseline with
explicit token and latency cost accounting, applies deterministic checks, and
optionally runs a pairwise model judge.
"""

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
    ArmResult,
    CaseResult,
    EvalReport,
    render_report_text,
)

__all__ = [
    "ArmResult",
    "CaseResult",
    "CheckOutcome",
    "EvalCase",
    "EvalChecks",
    "EvalCorpus",
    "EvalReport",
    "JudgeVerdict",
    "evaluate_checks",
    "judge_pair",
    "load_corpus",
    "render_report_text",
    "run_evaluation",
]
