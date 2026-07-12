# Canonical Data Models

Use Pydantic v2 models with strict validation unless this document explicitly allows coercion. Public models should be serializable to JSON.

Field names below are canonical. Minor internal helper models may be added without changing public output.

## 1. Enumerations

### TaskComplexity

```text
simple
moderate
complex
multi_step
high_stakes
```

### AmbiguityLevel

```text
none
low
medium
high
```

### RiskLevel

```text
low
medium
high
```

### ClarificationAction

```text
proceed
ask_clarification
refuse_or_redirect
```

### PipelineStatus

```text
completed
clarification_required
refused
failed
completed_with_warnings
```

### CriticStatus

```text
passed
revision_recommended
failed
not_checked
skipped
```

### OutputMode

```text
text
markdown
json
```

### StrategyId

The exact MVP values are listed in `MVP.md` and registered in code. Unknown strategy IDs are invalid.

### ModelRole

```text
understanding
worker
critic
revision
```

## 2. PromptRequest

Represents caller input before model understanding.

```json
{
  "prompt": "Help me choose between SQLite and PostgreSQL",
  "context": null,
  "requested_output_mode": null,
  "conversation_id": null,
  "metadata": {}
}
```

Fields:

- `prompt: str` — required, non-empty after normalization.
- `context: str | null` — caller-supplied context; no retrieval occurs.
- `requested_output_mode: OutputMode | null` — explicit caller override.
- `conversation_id: str | null` — opaque metadata only; not persisted.
- `metadata: dict[str, JsonValue]` — bounded caller metadata; not injected into prompts unless explicitly selected.

## 3. IntakeResult

```json
{
  "request": {"prompt": "...", "context": null, "requested_output_mode": null, "conversation_id": null, "metadata": {}},
  "normalized_prompt": "...",
  "normalized_context": null,
  "warnings": []
}
```

## 4. TaskUnderstanding

Describes what the model believes the user is trying to accomplish.

```json
{
  "user_goal": "Choose the more appropriate database for the described application",
  "intent": "decision support",
  "task_type": "comparison",
  "complexity": "moderate",
  "ambiguity": "medium",
  "risk_level": "low",
  "risk_categories": [],
  "missing_information": ["expected concurrency", "deployment environment"],
  "assumptions": [],
  "uncertainties": ["The scale of the application is unspecified"],
  "concise_rationale": "The user is comparing two technologies and needs a conditional recommendation."
}
```

Constraints:

- free-text labels are concise;
- list counts and string lengths are bounded;
- `concise_rationale` is not hidden chain-of-thought and should be no more than a few sentences.

## 5. ClarificationDecision

```json
{
  "action": "proceed",
  "question": null,
  "reason": "A useful conditional comparison can be provided with explicit assumptions."
}
```

Consistency rules:

- `ask_clarification` requires one non-empty question;
- `proceed` requires `question` to be null;
- `refuse_or_redirect` requires a concise user-facing reason or redirect instruction;
- only one clarification question is returned in the MVP.

## 6. OutputContract

```json
{
  "mode": "markdown",
  "structure": "comparison with recommendation and decision criteria",
  "tone": "practical and neutral",
  "length": "medium",
  "audience": "software developer"
}
```

Fields are bounded descriptive strings. `mode` must be supported by the strategy and caller override.

## 7. ExecutionPlan

The central model-produced object.

```json
{
  "schema_version": 1,
  "understanding": {"...": "TaskUnderstanding"},
  "clarification": {"...": "ClarificationDecision"},
  "strategy": "comparison",
  "worker_role": "worker",
  "output_contract": {"...": "OutputContract"},
  "must_include": ["tradeoffs", "conditional recommendation"],
  "must_avoid": ["pretending missing scale requirements are known"],
  "quality_criteria": [
    "Distinguish embedded/local use from client-server use",
    "State assumptions",
    "Give a recommendation conditional on expected workload"
  ],
  "critic_required": true
}
```

Rules:

- `schema_version` must equal `1`;
- `strategy` must be registered;
- `worker_role` must be a configured allowed role, normally `worker`;
- caller output-mode override takes precedence when compatible;
- plan lists are deduplicated and bounded;
- `critic_required` may be overridden by deterministic runtime policy;
- clarification/refusal plans do not proceed to worker generation.

## 8. ValidatedExecutionPlan

Application-owned wrapper around the accepted plan:

```json
{
  "plan": {"...": "ExecutionPlan"},
  "policy_changes": [],
  "validation_warnings": [],
  "used_safe_fallback": false
}
```

## 9. ModelRequest

Provider-neutral request:

```json
{
  "role": "worker",
  "model_name": "local_general",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "temperature": 0.2,
  "max_output_tokens": 4096,
  "timeout_seconds": 180,
  "request_kind": "worker"
}
```

## 10. ModelResponse

```json
{
  "text": "...",
  "model": "server-returned-model-or-null",
  "finish_reason": "stop",
  "usage": {
    "input_tokens": null,
    "output_tokens": null,
    "total_tokens": null
  },
  "provider_metadata": {}
}
```

Provider metadata must be sanitized.

## 11. PromptPlan

Used by the `plan` CLI command and worker stage.

```json
{
  "strategy": "comparison",
  "worker_role": "worker",
  "system_prompt": "...",
  "user_prompt": "...",
  "output_contract": {"...": "OutputContract"},
  "quality_criteria": []
}
```

Full prompt fields may be omitted/redacted in normal JSON output according to trace policy.

## 12. DraftResponse

```json
{
  "text": "...",
  "model_name": "local_general",
  "role": "worker",
  "warnings": [],
  "usage": {"input_tokens": null, "output_tokens": null, "total_tokens": null}
}
```

## 13. CriticIssue

```json
{
  "code": "missing_constraint",
  "severity": "major",
  "message": "The draft does not state its assumptions.",
  "criterion": "State assumptions"
}
```

Severity values: `minor`, `major`, `critical`.

## 14. CriticResult

```json
{
  "schema_version": 1,
  "passes": false,
  "issues": [{"...": "CriticIssue"}],
  "violated_criteria": ["State assumptions"],
  "revision_recommended": true,
  "revision_instruction": "Add explicit workload assumptions and make the recommendation conditional on them.",
  "concise_summary": "The comparison is useful but overconfident because assumptions are implicit."
}
```

Consistency rules:

- `passes=true` implies `revision_recommended=false` and no major/critical issues;
- revision requires a non-empty concise instruction;
- critic output must not include hidden reasoning.

## 15. QualityResult

Application-owned critic outcome:

```json
{
  "status": "revision_recommended",
  "critic_result": {"...": "CriticResult"},
  "warnings": []
}
```

## 16. FinalResponse

```json
{
  "status": "completed",
  "text": "...",
  "clarification_question": null,
  "strategy": "comparison",
  "roles": {
    "understanding": "local_general",
    "worker": "local_general",
    "critic": "local_general",
    "revision": "local_general"
  },
  "assumptions": [],
  "warnings": [],
  "critic_status": "passed",
  "revision_performed": false,
  "used_safe_fallback": false,
  "trace": null
}
```

For clarification, `text` may be empty and `clarification_question` is required.

## 17. Trace models

Trace consists of ordered events with:

- stage;
- event name;
- status;
- monotonic duration;
- attempt number;
- sanitized details;
- warning/error code.

Never store secret values in a trace model.
