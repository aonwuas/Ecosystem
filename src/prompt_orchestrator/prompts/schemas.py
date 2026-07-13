"""Exact structured-output schema guidance for model prompts."""

EXECUTION_PLAN_JSON_SKELETON = """{
  "schema_version": 1,
  "understanding": {
    "user_goal": "...",
    "intent": "...",
    "task_type": "...",
    "complexity": "simple | moderate | complex | multi_step | high_stakes",
    "ambiguity": "none | low | medium | high",
    "risk_level": "low | medium | high",
    "risk_categories": [],
    "missing_information": [],
    "assumptions": [],
    "uncertainties": [],
    "concise_rationale": "..."
  },
  "clarification": {
    "action": "proceed | ask_clarification | refuse_or_redirect",
    "question": null,
    "reason": "..."
  },
  "strategy": "draft_generation",
  "worker_role": "worker",
  "output_contract": {
    "mode": "text | markdown | json",
    "structure": "...",
    "tone": "...",
    "length": "...",
    "audience": "..."
  },
  "must_include": [],
  "must_avoid": [],
  "quality_criteria": [],
  "critic_required": true
}"""


EXECUTION_PLAN_SCHEMA_RULES = """Rules:
- Return exactly one JSON object matching the skeleton above.
- understanding must be an object, not a string.
- clarification must be an object with action and reason; it may not be null or empty.
- If clarification.action is "proceed", clarification.question must be null.
- If clarification.action is "ask_clarification", clarification.question must contain
  one focused question.
- output_contract must be an object with mode, structure, tone, length, and audience.
- output_contract may not use format or content fields.
- quality_criteria, must_include, and must_avoid must be arrays, not strings.
- Do not add top-level rationale, assumptions, uncertainties, summary, or
  explanation fields.
- Put assumptions and uncertainties inside understanding only."""


def execution_plan_schema_contract() -> str:
    """Return exact schema guidance for ExecutionPlan model outputs."""
    return (
        "Exact required JSON skeleton:\n"
        f"{EXECUTION_PLAN_JSON_SKELETON}\n\n"
        f"{EXECUTION_PLAN_SCHEMA_RULES}"
    )
