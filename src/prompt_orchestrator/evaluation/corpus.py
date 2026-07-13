"""Evaluation corpus schema and loading.

A corpus is a set of evaluation cases. Each case carries the prompt to run plus
deterministic expectations that can be checked without a live model, so the core
of the evaluation runs offline. Optional rubric text guides the opt-in model
judge.
"""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import Field

from prompt_orchestrator.domain._base import BoundedText, DomainModel, ShortText
from prompt_orchestrator.domain.enums import PipelineStatus
from prompt_orchestrator.exceptions import InputError

MAX_CASES = 500


class EvalChecks(DomainModel):
    """Deterministic expectations applied to an answer."""

    must_include: list[ShortText] = Field(default_factory=list, max_length=20)
    must_avoid: list[ShortText] = Field(default_factory=list, max_length=20)
    min_length: int | None = Field(default=None, ge=0, strict=True)
    max_length: int | None = Field(default=None, ge=0, strict=True)
    expect_status: PipelineStatus | None = None


class EvalCase(DomainModel):
    """One evaluation case."""

    id: ShortText
    prompt: BoundedText
    context: str | None = None
    category: ShortText | None = None
    rubric: ShortText | None = None
    checks: EvalChecks = Field(default_factory=EvalChecks)


class EvalCorpus(DomainModel):
    """An ordered, id-unique collection of evaluation cases."""

    cases: list[EvalCase] = Field(min_length=1, max_length=MAX_CASES)


def load_corpus(path: str | Path) -> EvalCorpus:
    """Load a corpus from a YAML file or a directory of YAML files."""
    target = Path(path)
    if target.is_dir():
        raw_cases = _load_directory(target)
    elif target.is_file():
        raw_cases = _load_file(target)
    else:
        raise InputError(
            f"Evaluation corpus path '{target}' does not exist.",
            code="EVAL_CORPUS_NOT_FOUND",
        )
    if not raw_cases:
        raise InputError(
            "Evaluation corpus contains no cases.",
            code="EVAL_CORPUS_EMPTY",
        )
    cases = [_parse_case(item) for item in raw_cases]
    _reject_duplicate_ids(cases)
    return EvalCorpus(cases=cases)


def _load_directory(directory: Path) -> list[object]:
    raw_cases: list[object] = []
    for file in sorted(directory.glob("*.yaml")):
        raw_cases.extend(_load_file(file))
    return raw_cases


def _load_file(file: Path) -> list[object]:
    try:
        raw = yaml.safe_load(file.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError(
            f"Could not read evaluation corpus file '{file}'.",
            code="EVAL_CORPUS_READ_FAILED",
        ) from exc
    if raw is None:
        return []
    if isinstance(raw, dict) and "cases" in raw:
        raw = raw["cases"]
    if not isinstance(raw, list):
        raise InputError(
            f"Evaluation corpus file '{file}' must be a list of cases "
            "or a mapping with a 'cases' list.",
            code="EVAL_CORPUS_INVALID",
        )
    return raw


def _parse_case(item: object) -> EvalCase:
    if not isinstance(item, dict):
        raise InputError(
            "Each evaluation case must be a mapping.",
            code="EVAL_CORPUS_INVALID",
        )
    try:
        return EvalCase.model_validate(item)
    except ValueError as exc:
        raise InputError(
            f"Invalid evaluation case: {exc}",
            code="EVAL_CORPUS_INVALID",
        ) from exc


def _reject_duplicate_ids(cases: list[EvalCase]) -> None:
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise InputError(
                f"Duplicate evaluation case id '{case.id}'.",
                code="EVAL_CORPUS_DUPLICATE_ID",
            )
        seen.add(case.id)
