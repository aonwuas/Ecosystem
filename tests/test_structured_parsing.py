from __future__ import annotations

import pytest

from prompt_orchestrator.domain import CriticResult, ExecutionPlan
from prompt_orchestrator.exceptions import StructuredOutputError
from prompt_orchestrator.parsing import (
    RepairBudget,
    build_repair_request_data,
    extract_json_object_text,
    parse_json_object,
    strip_markdown_json_fence,
    validate_structured_output,
)


def execution_plan_json() -> str:
    return """
{
  "schema_version": 1,
  "understanding": {
    "user_goal": "Choose the more appropriate database",
    "intent": "decision support",
    "task_type": "comparison",
    "complexity": "moderate",
    "ambiguity": "medium",
    "risk_level": "low",
    "risk_categories": [],
    "missing_information": ["expected concurrency"],
    "assumptions": [],
    "uncertainties": ["Scale is unspecified"],
    "concise_rationale": "The user is comparing technologies."
  },
  "clarification": {
    "action": "proceed",
    "question": null,
    "reason": "A conditional answer can be useful."
  },
  "strategy": "comparison",
  "output_contract": {
    "mode": "markdown",
    "structure": "comparison with recommendation",
    "tone": "practical and neutral",
    "length": "medium",
    "audience": "software developer"
  },
  "must_include": ["tradeoffs"],
  "must_avoid": ["pretending missing requirements are known"],
  "quality_criteria": ["State assumptions"],
  "critic_required": true
}
"""


def critic_json() -> str:
    return """
{
  "schema_version": 1,
  "passes": false,
  "issues": [
    {
      "code": "missing_constraint",
      "severity": "major",
      "message": "The draft does not state assumptions.",
      "criterion": "State assumptions"
    }
  ],
  "violated_criteria": ["State assumptions"],
  "revision_recommended": true,
  "revision_instruction": "Add explicit assumptions.",
  "concise_summary": "Useful but overconfident."
}
"""


def test_valid_json_is_parsed_directly() -> None:
    parsed = parse_json_object(execution_plan_json())

    assert parsed["schema_version"] == 1
    assert parsed["strategy"] == "comparison"


def test_common_fenced_json_is_accepted() -> None:
    fenced = f"```json\n{execution_plan_json()}\n```"

    result = validate_structured_output(fenced, ExecutionPlan)

    assert result.value.strategy == "comparison"
    assert "worker_role" not in result.raw_object


def test_limited_surrounding_prose_is_accepted() -> None:
    noisy = f"Here is the object:\n{critic_json()}\nDone."

    result = validate_structured_output(noisy, CriticResult)

    assert result.value.revision_recommended is True


def test_braces_inside_json_strings_do_not_split_candidates() -> None:
    text = '{"schema_version": 1, "passes": true, "issues": [], '
    text += '"violated_criteria": [], "revision_recommended": false, '
    text += '"revision_instruction": null, '
    text += '"concise_summary": "Literal braces { like this } are text."}'

    result = validate_structured_output(text, CriticResult)

    assert "Literal braces" in result.value.concise_summary


def test_optional_markdown_fence_removal_preserves_unfenced_text() -> None:
    plain = '{"ok": true}'

    assert strip_markdown_json_fence(plain) == plain
    assert strip_markdown_json_fence('```json\n{"ok": true}\n```') == '{"ok": true}'


def test_ambiguous_multiple_top_level_objects_are_rejected() -> None:
    with pytest.raises(StructuredOutputError, match="Multiple"):
        extract_json_object_text('{"a": 1} and {"b": 2}')


def test_malformed_json_produces_concise_parse_diagnostic() -> None:
    with pytest.raises(StructuredOutputError, match="line 1, column"):
        parse_json_object('{"a": }')


def test_truncated_json_is_rejected() -> None:
    with pytest.raises(StructuredOutputError, match="No complete"):
        parse_json_object('{"schema_version": 1')


def test_missing_field_output_produces_repair_diagnostics() -> None:
    invalid = '{"schema_version": 1, "strategy": "comparison"}'

    with pytest.raises(StructuredOutputError) as error:
        validate_structured_output(invalid, ExecutionPlan)

    repair = build_repair_request_data(
        invalid_response=invalid,
        error=error.value,
        model_type=ExecutionPlan,
    )
    assert "understanding" in str(error.value)
    assert repair.schema_name == "ExecutionPlan"
    assert repair.invalid_response == invalid
    assert "Required fields" in repair.required_json_shape
    assert repair.validation_errors


def test_extra_field_output_is_rejected_by_pydantic_schema() -> None:
    invalid = critic_json().replace(
        '"concise_summary": "Useful but overconfident."',
        '"concise_summary": "Useful but overconfident.", "extra": true',
    )

    with pytest.raises(StructuredOutputError, match="extra"):
        validate_structured_output(invalid, CriticResult)


def test_invalid_consistency_rule_is_reported() -> None:
    invalid = critic_json().replace('"passes": false', '"passes": true')

    with pytest.raises(StructuredOutputError, match="revision_recommended"):
        validate_structured_output(invalid, CriticResult)


def test_repair_budget_helper_allows_one_repair() -> None:
    budget = RepairBudget(max_attempts=1)

    consumed = budget.consume()

    assert budget.can_repair() is True
    assert consumed.can_repair() is False
    with pytest.raises(StructuredOutputError, match="exhausted"):
        consumed.consume()


def test_no_eval_or_code_execution_is_used() -> None:
    payload = "__import__('os').system('echo unsafe')"

    with pytest.raises(StructuredOutputError):
        parse_json_object(payload)
