"""Validate extracted model JSON against Pydantic schemas."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from prompt_orchestrator.exceptions import StructuredOutputError
from prompt_orchestrator.parsing.json_extract import extract_json_object_text
from prompt_orchestrator.stages.trace import current_llm_io_recorder


@dataclass(frozen=True)
class StructuredValidationResult[ModelT: BaseModel]:
    """Validated object plus the extracted raw JSON object data."""

    value: ModelT
    raw_object: dict[str, object]


@dataclass(frozen=True)
class RepairRequestData:
    """Data needed to ask a model for one structured-output repair."""

    schema_name: str
    invalid_response: str
    validation_errors: tuple[str, ...]
    required_json_shape: str


@dataclass(frozen=True)
class RepairBudget:
    """Bounded helper for structured-output repair attempts."""

    max_attempts: int = 1
    attempts_used: int = 0

    def can_repair(self) -> bool:
        return self.attempts_used < self.max_attempts

    def consume(self) -> RepairBudget:
        if not self.can_repair():
            raise StructuredOutputError(
                "Structured-output repair budget is exhausted.",
                code="STRUCTURED_REPAIR_BUDGET_EXHAUSTED",
            )
        return RepairBudget(
            max_attempts=self.max_attempts,
            attempts_used=self.attempts_used + 1,
        )


def validate_structured_output[ModelT: BaseModel](
    text: str,
    model_type: type[ModelT],
) -> StructuredValidationResult[ModelT]:
    """Extract one JSON object and validate it as the requested Pydantic model."""
    try:
        extracted = extract_json_object_text(text)
        _record_extracted_json(extracted.text)
        raw_object = _parse_extracted_json(extracted.text)
    except StructuredOutputError as exc:
        _record_validation_error(str(exc))
        raise

    try:
        value = model_type.model_validate(raw_object)
    except ValidationError as exc:
        diagnostics = _validation_error_messages(exc)
        error = StructuredOutputError(
            "Structured output failed schema validation: " + "; ".join(diagnostics),
            code="STRUCTURED_SCHEMA_INVALID",
        )
        _record_validation_error(str(error))
        raise error from exc

    return StructuredValidationResult(value=value, raw_object=raw_object)


def _parse_extracted_json(text: str) -> dict[str, object]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(
            f"JSON parse error at line {exc.lineno}, column {exc.colno}: {exc.msg}",
            code="STRUCTURED_JSON_PARSE_ERROR",
        ) from exc
    if not isinstance(parsed, dict):
        raise StructuredOutputError(
            "Structured output must be a JSON object.",
            code="STRUCTURED_JSON_NOT_OBJECT",
        )
    return parsed


def build_repair_request_data(
    *,
    invalid_response: str,
    error: StructuredOutputError,
    model_type: type[BaseModel],
) -> RepairRequestData:
    """Build repair prompt data without performing a repair model call."""
    return RepairRequestData(
        schema_name=model_type.__name__,
        invalid_response=invalid_response,
        validation_errors=(str(error),),
        required_json_shape=_schema_shape_summary(model_type),
    )


def _validation_error_messages(error: ValidationError) -> list[str]:
    messages: list[str] = []
    for detail in error.errors(include_url=False):
        location = ".".join(str(part) for part in detail["loc"])
        message = str(detail["msg"])
        if location:
            messages.append(f"{location}: {message}")
        else:
            messages.append(message)
    return messages


def _record_extracted_json(text: str) -> None:
    recorder = current_llm_io_recorder()
    if recorder is not None:
        recorder.record_extracted_json(text)


def _record_validation_error(error: str) -> None:
    recorder = current_llm_io_recorder()
    if recorder is not None:
        recorder.record_validation_error(error)


def _schema_shape_summary(model_type: type[BaseModel]) -> str:
    schema = model_type.model_json_schema()
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    field_names = sorted(properties) if isinstance(properties, dict) else []
    required_names = (
        [str(item) for item in required] if isinstance(required, list) else []
    )
    return (
        f"Return exactly one JSON object matching {model_type.__name__}. "
        f"Required fields: {', '.join(required_names) or 'none'}. "
        f"Allowed top-level fields include: {', '.join(field_names) or 'none'}."
    )
