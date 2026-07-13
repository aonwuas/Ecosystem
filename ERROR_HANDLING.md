# Error Handling and Retry Policy

## 1. Principles

- Fail early on configuration errors.
- Keep transport retries separate from semantic retries.
- Bound every retry and revision loop.
- Return structured errors with stable codes.
- Preserve the best valid answer when a later optional stage fails.
- Never hide degraded operation from JSON/trace output.

## 2. Exception categories

Recommended domain exceptions:

- `ConfigurationError`
- `InputError`
- `ProviderError`
- `ProviderTimeoutError`
- `ProviderAuthenticationError`
- `StructuredOutputError`
- `ExecutionPlanValidationError`
- `PolicyError`
- `PromptRenderError`
- `PipelineStateError`
- `CriticError`
- `RevisionError`

CLI maps them to documented non-zero exit codes.

## 3. Configuration failures

Examples:

- missing config file;
- unknown provider type;
- model references missing provider;
- role references missing model;
- required environment secret missing;
- invalid retry limit;
- unsupported strategy override.

Behavior: fail before any model call and print a concise actionable message.

## 4. Input failures

Empty or whitespace-only prompt: fail with input error.

Prompt/context size may be bounded by configuration. When exceeded, fail clearly; the MVP does not automatically summarize or truncate user input unless explicitly documented.

## 5. HTTP/provider failures

### Transient retry

At most one retry for configured transient conditions such as connection reset, timeout, or selected 5xx responses.

Do not retry:

- authentication/authorization failures;
- invalid endpoint URL;
- most 4xx responses;
- semantic refusal/content errors;
- caller cancellation.

Use short bounded backoff. Record retries in trace.

## 6. Understanding structured-output failure

Sequence:

1. parse and validate initial response;
2. if invalid and repair budget is one, call understanding role with repair prompt;
3. parse and validate repaired response;
4. if still invalid:
   - `understanding_failure_mode=clarify`: return
     `FinalResponse(status=clarification_required)` with a concise request for
     the user to restate the goal, constraints, and desired output format.

No third attempt.

Default behavior does not call the worker, critic, or revision stage after an
understanding structured-output failure.

## 7. Execution-plan policy failure

When a valid schema violates deterministic policy:

- correct only policy-owned fields when a safe deterministic correction exists;
- record each correction in `policy_changes`;
- reject the plan when correction would require guessing user intent;
- never ask the model to override application safety policy.

Examples of safe corrections:

- force critic on for high-stakes output;
- replace an incompatible output mode with caller override;
- cap list lengths or revision counts.

## 8. Worker failure

If worker call fails after permitted transport retry, the pipeline fails. There is no alternate worker fallback model in the MVP.

If worker returns empty text, treat it as a worker failure. Do not pass empty output to critic.

## 9. Critic failure

When critic is disabled: mark `skipped`.

When critic call or structured parsing fails:

- if `strict_critic=false`: return worker draft with `critic_status=not_checked`, warning, and completed-with-warnings status;
- if `strict_critic=true`: fail the pipeline.

One critic structured-output repair attempt may be used if runtime repair budget permits. It does not count as a revision.

## 10. Revision failure

If revision fails or returns empty text:

- preserve original worker draft;
- mark revision failure in warnings and trace;
- return completed-with-warnings unless strict future policy says otherwise.

No second revision attempt beyond the configured maximum of one.

## 11. Deterministic final checks

Before finalization:

- answer text is non-empty for completed status;
- clarification question is present for clarification status;
- refusal has user-facing text;
- output JSON mode serializes successfully;
- no secret values appear in trace/config rendering;
- pipeline state transition is legal.

## 12. Error output

Text mode:

```text
Error [CONFIG_ROLE_NOT_FOUND]: Role 'critic' references unknown model 'reviewer_api'.
```

JSON mode:

```json
{
  "status": "failed",
  "error": {
    "code": "CONFIG_ROLE_NOT_FOUND",
    "message": "Role 'critic' references an unknown model.",
    "retryable": false
  }
}
```

Do not print stack traces unless an explicit debug flag is enabled.
