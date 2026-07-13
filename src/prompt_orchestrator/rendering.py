"""CLI output renderers."""

from __future__ import annotations

import json
from typing import Any

from prompt_orchestrator.domain import (
    FinalResponse,
    PromptPlan,
    Trace,
    ValidatedExecutionPlan,
)
from prompt_orchestrator.pipeline import PipelinePlanResult
from prompt_orchestrator.strategies import get_strategy


def render_json(value: object) -> str:
    """Render Pydantic models and plain values as stable JSON."""
    data = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    return json.dumps(data, indent=2, sort_keys=True)


def render_final_text(response: FinalResponse) -> str:
    """Render the user-facing final response."""
    if response.clarification_question is not None:
        return response.clarification_question
    if response.text:
        return response.text
    return response.status.value


def render_understand_text(plan: ValidatedExecutionPlan) -> str:
    """Render a compact understanding summary."""
    execution_plan = plan.plan
    status = (
        "clarification_required"
        if execution_plan.clarification.action.value == "ask_clarification"
        else "understood"
    )
    lines = [
        f"Status: {status}",
        f"Strategy: {execution_plan.strategy.value}",
        f"Worker role: {get_strategy(execution_plan.strategy).worker_role.value}",
        f"Goal: {execution_plan.understanding.user_goal}",
        f"Clarification: {execution_plan.clarification.action.value}",
    ]
    if execution_plan.clarification.question is not None:
        lines.append(f"Question: {execution_plan.clarification.question}")
    if plan.policy_changes:
        lines.append("Policy changes:")
        lines.extend(f"- {change}" for change in plan.policy_changes)
    if plan.validation_warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in plan.validation_warnings)
    return "\n".join(lines)


def render_plan_text(result: PipelinePlanResult) -> str:
    """Render a prompt plan or gate final response."""
    if result.final_response is not None:
        return render_final_text(result.final_response)
    if result.prompt_plan is None:
        return "No prompt plan available."
    return render_prompt_plan_text(result.prompt_plan)


def render_prompt_plan_text(plan: PromptPlan) -> str:
    """Render a worker prompt plan."""
    return "\n".join(
        [
            f"Strategy: {plan.strategy.value}",
            f"Worker role: {plan.worker_role.value}",
            "",
            "System prompt:",
            plan.system_prompt,
            "",
            "User prompt:",
            plan.user_prompt,
        ]
    )


def attach_trace_json(payload: dict[str, Any], trace: Trace | None) -> dict[str, Any]:
    """Attach trace data to an existing JSON payload."""
    if trace is not None:
        payload["trace"] = trace.model_dump(mode="json")
    return payload
