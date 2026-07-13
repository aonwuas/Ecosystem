# Testing Strategy

## 1. Objectives

Tests must prove that orchestration behavior is deterministic around nondeterministic model outputs. The default suite must run without internet access or live model servers.

## 2. Test categories

### Unit tests

Cover:

- configuration loading and validation;
- environment-secret resolution and redaction;
- role/model/provider resolution;
- domain-model validation;
- JSON extraction;
- structured-output repair decision;
- strategy registration;
- prompt rendering;
- policy corrections/rejections;
- state transitions;
- error-to-exit-code mapping;
- trace redaction.

### Integration tests

Use scripted clients to cover:

- normal understand → worker → critic pass;
- clarification required;
- refusal/redirect;
- invalid understanding JSON followed by successful repair;
- invalid understanding JSON followed by safe fallback;
- invalid understanding JSON followed by failure;
- critic recommends revision;
- revision succeeds;
- revision fails and original draft is preserved;
- critic fails in non-strict mode;
- critic fails in strict mode;
- role mappings all point to one model;
- roles point to different named models;
- CLI text output;
- CLI JSON output;
- trace output;
- stdin prompt input.

### Live smoke tests

Optional and excluded from default test run. They may validate an OpenAI-compatible endpoint when explicitly configured. Mark them with `@pytest.mark.live`.

Run live tests explicitly with:

```bash
PROMPT_ORCHESTRATOR_LIVE_CONFIG=examples/config.local-llama.yaml pytest -m live
```

Without `PROMPT_ORCHESTRATOR_LIVE_CONFIG`, the live smoke test skips itself.

## 3. Test clients

### MockModelClient

Returns simple fixed responses and records requests.

### ScriptedModelClient

Consumes an ordered script of expected request kinds and responses/errors. It must fail a test when calls occur out of order or exceed the script.

Example script concept:

```yaml
- expect: understanding
  respond_json: {...ExecutionPlan...}
- expect: worker
  respond_text: "Draft answer"
- expect: critic
  respond_json: {...CriticResult...}
```

## 4. Fixtures

Keep reusable fixtures under `tests/fixtures/`:

- valid and invalid configs;
- execution plans for each strategy family;
- critic pass/fail responses;
- fenced and noisy JSON responses;
- large/invalid field cases;
- scripted complete runs.

Fixtures must not contain secrets.

## 5. Prompt tests

Avoid brittle snapshots of every word. Test structural invariants:

- correct application instruction is present;
- user prompt appears only inside delimiters;
- context has separate delimiters;
- output schema or contract is present;
- constraints and quality criteria are included;
- missing template variables fail;
- arbitrary template path cannot be supplied.

Small approved snapshots may be used for representative templates.

## 6. HTTP client tests

Use HTTPX mock transport or an equivalent local fake. Test:

- correct endpoint path;
- authorization header when configured;
- no authorization header when absent;
- timeout mapping;
- response parsing;
- non-2xx error mapping;
- transient retry count;
- sanitized error messages.

## 7. CLI tests

Invoke the installed entry point or `python -m prompt_orchestrator` in tests. Verify:

- help output;
- stable exit codes;
- configuration errors;
- `config validate`;
- `understand`;
- `plan`;
- `run`;
- `--stdin`;
- `--json`;
- `--trace`.

## 8. Quality gates

By final milestone:

```bash
pytest
pytest --cov=src/prompt_orchestrator --cov-report=term-missing --cov-fail-under=85
ruff check .
ruff format --check .
mypy src
```

Target at least 85% line coverage for `src/prompt_orchestrator`, with stronger
emphasis on branches in policy, parsing, and error handling. Coverage must not
encourage meaningless tests.

## 9. No test shortcuts

- Do not make network access part of the default suite.
- Do not sleep for retries; inject or patch backoff.
- Do not test implementation-private wording when behavior is the requirement.
- Do not disable validation to simplify fixtures.
- Do not delete tests to accommodate implementation drift.

## 10. Documentation consistency at completion

Milestone and roadmap-phase completion must include a documentation review.
Update `PROJECT_STATE.md` when implementation changes affect architecture,
configuration, schemas, prompts, pipeline flow, error behavior, public
interfaces, test commands, or roadmap status.

Do not add brittle tests that compare all documentation prose to source code.
Where practical, prefer lightweight tests for documented public commands,
configuration examples, public schemas, or prompt contracts, and use a review
checklist for broader documentation consistency.
