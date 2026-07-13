# Project State

## 1. Document purpose and maintenance contract

`ROADMAP.md` describes intended future work. `PROJECT_STATE.md` describes the
current implemented system in this repository. Planners should read both files:
`ROADMAP.md` for direction and phases, and this file for what actually exists
today.

This file must be updated whenever implementation changes make it inaccurate.
The repository remains the ultimate source of truth; this document is a
grounded handoff summary, not a replacement for inspecting code during
implementation.

- Project state schema version: 1
- Last verified date: 2026-07-13
- Current git commit when verified: `d400530`
- Current branch when verified: `main`
- Package/application version: `0.1.0` from `pyproject.toml` and
  `src/prompt_orchestrator/__init__.py`
- Verification scope: all files returned by `rg --files` were inspected.

## 2. Product summary

Prompt Orchestrator is currently a Python 3.12+ CLI-first prompt orchestration
runtime. It accepts a user prompt, asks an understanding model for a structured
`ExecutionPlan`, validates that plan with Pydantic and deterministic policy,
builds a strategy-specific worker prompt, generates a draft, optionally reviews
that draft with a critic model, optionally performs one revision, and returns a
final response.

Implemented user interfaces:

- CLI module invocation: `python -m prompt_orchestrator ...` via
  `src/prompt_orchestrator/__main__.py`.
- CLI console script: `prompt-orchestrator ...` from `[project.scripts]` in
  `pyproject.toml` when the Python Scripts directory is on `PATH`.
- Library API: `PipelineRunner` in
  `src/prompt_orchestrator/pipeline/runner.py`, stage callables under
  `src/prompt_orchestrator/stages/`, provider-neutral domain models under
  `src/prompt_orchestrator/domain/`, and provider clients under
  `src/prompt_orchestrator/clients/`.

Current operating mode:

- Synchronous, local process, single request per CLI invocation.
- Configuration-driven provider/model/role resolution.
- No persisted task state.
- Default tests use deterministic mock/scripted clients and do not require
  network access.
- Optional live smoke tests can call an OpenAI-compatible endpoint when
  `PROMPT_ORCHESTRATOR_LIVE_CONFIG` is set.

Major limitations:

- No persistent sessions or task state.
- No multi-step task decomposition.
- No model fallback chains.
- No API service, worker queue, streaming, cancellation, or concurrency control.
- No retrieval, external tools, databases, web UI, user accounts, or memory.
- Strategy behavior is mostly metadata plus prompt templates; there are no
  deeply different execution paths per strategy beyond prompt selection,
  supported output modes, default quality criteria, and critic policy flags.

Explicitly excluded by current docs and code:

- RAG, embeddings, vector databases, document indexing, tools, shell/browser
  access, filesystem mutation initiated by the runtime, persistent memory,
  database storage, service mode, web UI, streaming, automatic hosted API
  escalation, and hidden chain-of-thought capture.

## 3. Current end-to-end flow

Runtime flow for `prompt-orchestrator run`:

```text
Prompt text or stdin
  -> PromptRequest
  -> normalize_input
  -> run_understanding_stage
  -> validate_structured_output(ExecutionPlan)
  -> evaluate_execution_plan_policy
  -> finalize_plan_gate if clarification/refusal
  -> build_worker_prompt_plan
  -> run_worker_stage
  -> run_quality_stage
      -> run_critic_stage
      -> run_revision_stage at most once when recommended
  -> finalize_completed
  -> CLI renderer
```

Primary stage implementations:

- Intake: `normalize_input` in `src/prompt_orchestrator/stages/intake.py`.
- Understanding: `run_understanding_stage` in
  `src/prompt_orchestrator/stages/understanding.py`.
- Structured parsing: `validate_structured_output` in
  `src/prompt_orchestrator/parsing/structured.py`.
- Deterministic policy: `evaluate_execution_plan_policy` in
  `src/prompt_orchestrator/policy/execution_plan.py`.
- Worker prompt planning/generation: `build_worker_prompt_plan` and
  `run_worker_stage` in `src/prompt_orchestrator/stages/worker.py`.
- Critic: `run_critic_stage` in `src/prompt_orchestrator/stages/critic.py`.
- Revision: `run_revision_stage` in
  `src/prompt_orchestrator/stages/revision.py`.
- Quality coordination: `run_quality_stage` in
  `src/prompt_orchestrator/stages/quality.py`.
- Finalization: `finalize_plan_gate`, `finalize_completed`, and
  `finalize_failed` in `src/prompt_orchestrator/stages/finalizer.py`.
- Pipeline orchestration: `PipelineRunner.plan` and `PipelineRunner.run` in
  `src/prompt_orchestrator/pipeline/runner.py`.
- CLI entry: `main` and `build_parser` in `src/prompt_orchestrator/cli.py`.

Branching behavior:

- Clarification: if `ExecutionPlan.clarification.action` is
  `ask_clarification`, `finalize_plan_gate` returns a
  `FinalResponse(status=clarification_required)` and no worker call occurs.
- Refusal/redirect: if action is `refuse_or_redirect`, finalization returns
  `FinalResponse(status=refused)` and no worker call occurs.
- Proceed: worker stage runs, then quality stage runs.
- Critic: skipped when `runtime.enable_critic` is false or
  `plan.critic_required` is false; otherwise called with structured
  `CriticResult` parsing and one repair attempt if configured.
- Revision: called at most once when critic recommends revision and
  `runtime.enable_revision` is true and `runtime.max_revision_attempts` is 1.
- Revision failure: original worker draft is preserved with a warning.
- Understanding failure: one repair attempt if
  `runtime.structured_output_repair_attempts` is 1; then
  `runtime.understanding_failure_mode=clarify` produces
  `FinalResponse(status=clarification_required)` and no worker, critic, or
  revision call occurs.
- Critic failure: degraded result with `critic_status=not_checked` when
  `runtime.strict_critic=false`; failed pipeline when strict.
- Worker failure: failed pipeline; no alternate worker fallback exists.

Finalization behavior:

- `finalize_completed` builds a `FinalResponse` with status `completed` or
  `completed_with_warnings`.
- `finalize_plan_gate` builds clarification/refusal final responses.
- `finalize_failed` wraps controlled `PromptOrchestratorError` failures into a
  failed `FinalResponse` for `PipelineRunner`.
- The top-level CLI catches controlled exceptions that occur outside runner
  finalization, maps them to exit codes, and prints concise errors.

## 4. Repository map

Important root files:

- `pyproject.toml`: package metadata, dependency lists, console script,
  pytest, Ruff, and mypy configuration. Stable.
- `config.example.yaml`: OpenAI-compatible single-model sample config. Stable
  MVP example.
- `.env.example`: documents optional `OPENAI_API_KEY` environment variable.
  Stable.
- `.gitattributes`: LF normalization for text files. Stable.
- `README.md`: user-facing overview and CLI examples. Stable but must track
  implemented public behavior.
- `ROADMAP.md`: future roadmap phases. It exists in the working tree and is
  treated as authoritative future direction. It was untracked at verification.
- `CHECKPOINTS.md`: historical MVP milestone checklist. Stable historical
  record.

Source directories:

- `src/prompt_orchestrator/domain/`: Pydantic schemas and enums.
  Public symbols are exported from `domain/__init__.py`. Depends on Pydantic
  and local enum/base modules. Stable MVP surface.
- `src/prompt_orchestrator/config/`: YAML loading, config Pydantic models,
  role resolution, and sanitized summaries. Depends on PyYAML, Pydantic, and
  domain enums. Stable MVP surface.
- `src/prompt_orchestrator/clients/`: `ModelClient` protocol, mock/scripted
  clients, OpenAI-compatible HTTP client, diagnostic wrapper, and factory.
  Depends on config and domain model I/O. Stable MVP surface with future
  provider extension expected.
- `src/prompt_orchestrator/parsing/`: JSON extraction and schema validation.
  Depends on domain schemas through callers and on explicit LLM I/O recorder
  for diagnostics. Stable MVP surface.
- `src/prompt_orchestrator/policy/`: deterministic execution-plan validation
  and policy corrections. Depends on config, domain models, and strategies.
  Stable MVP surface.
- `src/prompt_orchestrator/prompts/`: package template loader, renderer,
  allowed-variable sets, and exact schema guidance helpers. Stable, likely to
  change as prompt contracts evolve.
- `src/prompt_orchestrator/templates/`: Markdown prompt templates for
  understanding, critic, revision, and each strategy. Package-controlled
  assets. Stable but prompt text is expected to evolve.
- `src/prompt_orchestrator/strategies/`: static strategy definitions and
  registry. Stable MVP surface; future strategy work will extend it.
- `src/prompt_orchestrator/stages/`: intake, understanding, worker, critic,
  revision, quality coordination, finalizer, and trace collectors. Stable MVP
  implementation surface.
- `src/prompt_orchestrator/pipeline/`: state machine and `PipelineRunner`.
  Stable library-level orchestration API.
- `src/prompt_orchestrator/cli.py`: argparse CLI and diagnostic flag wiring.
  Stable public interface.
- `src/prompt_orchestrator/rendering.py`: CLI text and JSON rendering helpers.
  Stable public-output helper, internal to CLI.

Tests:

- `tests/test_domain_models.py`: domain schema validation.
- `tests/test_config.py`: config loading, role resolution, secrets, CLI
  config validation.
- `tests/test_clients.py`: mock/scripted clients and OpenAI-compatible HTTP
  adapter.
- `tests/test_structured_parsing.py`: JSON extraction, fences, malformed
  output, schema failures, repair budget.
- `tests/test_prompts_and_strategies.py`: registry and template invariants.
- `tests/test_execution_plan_policy.py`: deterministic policy behavior.
- `tests/test_understanding_stage.py`: intake and understanding stage,
  repair, fallback, schema-skeleton prompt regression.
- `tests/test_worker_stage.py`: worker prompt planning and generation.
- `tests/test_critic_revision_stages.py`: critic, repair, strict mode,
  revision, revision failure.
- `tests/test_pipeline_runner.py`: end-to-end runner, state machine, trace.
- `tests/test_cli_commands.py`: CLI commands, JSON/text, stdin, traces, LLM I/O
  diagnostics, exit behavior.
- `tests/test_examples.py`: scripted examples.
- `tests/test_live_smoke.py`: opt-in live OpenAI-compatible smoke test.
- `tests/test_scaffold.py`: package import, CLI help, retained spec docs.

## 5. Domain models and schemas

All public domain models inherit from `DomainModel` in
`src/prompt_orchestrator/domain/_base.py`, which sets Pydantic
`extra="forbid"`, `frozen=True`, `populate_by_name=True`,
`str_strip_whitespace=True`, and `validate_default=True`. Shared bounds include
`MAX_TEXT_LENGTH=20000`, `MAX_SHORT_TEXT_LENGTH=500`, `MAX_LIST_ITEMS=20`, and
`MAX_METADATA_KEYS=50`.

Enums in `src/prompt_orchestrator/domain/enums.py`:

- `TaskComplexity`: `simple`, `moderate`, `complex`, `multi_step`,
  `high_stakes`. Created by understanding output or fallback plan; consumed by
  policy, worker prompts, and final metadata.
- `AmbiguityLevel`: `none`, `low`, `medium`, `high`. Created by understanding
  output or fallback; consumed by policy and worker prompt summary.
- `RiskLevel`: `low`, `medium`, `high`. Created by understanding output or
  fallback; consumed by policy for critic enforcement.
- `ClarificationAction`: `proceed`, `ask_clarification`,
  `refuse_or_redirect`. Created by understanding output; consumed by policy,
  worker gate, finalizer, and pipeline runner.
- `PipelineStatus`: `completed`, `clarification_required`, `refused`,
  `failed`, `completed_with_warnings`. Created by finalizer; consumed by CLI
  exit mapping and JSON/text output.
- `CriticStatus`: `passed`, `revision_recommended`, `failed`, `not_checked`,
  `skipped`. Created by critic/quality stages; consumed by finalizer and
  pipeline state transitions.
- `OutputMode`: `text`, `markdown`, `json`. Created by CLI/config/model plan;
  consumed by policy and strategy metadata.
- `StrategyId`: 17 MVP strategy identifiers matching the registry.
- `ModelRole`: `understanding`, `worker`, `critic`, `revision`. Created by
  config and model plans; consumed by role resolution and client routing.
- `CriticIssueSeverity`: `minor`, `major`, `critical`.

Request and intake models in `src/prompt_orchestrator/domain/requests.py`:

- `PromptRequest`: fields `prompt`, `context`, `requested_output_mode`,
  `conversation_id`, `metadata`. Created by CLI `_prompt_request_from_args` or
  library callers. Consumed by intake and policy. Pydantic validates non-empty
  prompt at construction for normal use; `normalize_input` also rejects empty
  normalized text.
- `IntakeResult`: fields `request`, `normalized_prompt`,
  `normalized_context`, `warnings`. Created by `normalize_input`; consumed by
  understanding, worker, critic, revision, and pipeline.

Execution-plan models in `src/prompt_orchestrator/domain/execution_plan.py`:

- `TaskUnderstanding`: fields `user_goal`, `intent`, `task_type`,
  `complexity`, `ambiguity`, `risk_level`, `risk_categories`,
  `missing_information`, `assumptions`, `uncertainties`,
  `concise_rationale`. Created by model understanding output or
  `_clarification_failure_plan`; consumed by policy, worker prompt builder,
  finalizer.
- `ClarificationDecision`: fields `action`, `question`, `reason`.
  Validator enforces `ask_clarification` requires a question and `proceed`
  requires `question=None`. Created by understanding output/fallback; consumed
  by policy, worker gate, and finalizer.
- `OutputContract`: fields `mode`, `structure`, `tone`, `length`, `audience`.
  Created by understanding output or clarification-failure plan; consumed by
  policy, worker prompt builder, and final response planning.
- `ExecutionPlan`: fields `schema_version`, `understanding`, `clarification`,
  `strategy`, `output_contract`, `must_include`, `must_avoid`,
  `quality_criteria`, `critic_required`. Validator requires
  `schema_version == 1`. Created from model JSON by
  `validate_structured_output` or by `_clarification_failure_plan`; consumed by
  policy. `worker_role` is not accepted from model output.
- `ValidatedExecutionPlan`: fields `plan`, `policy_changes`,
  `validation_warnings`, `used_safe_fallback`. Created by
  `evaluate_execution_plan_policy`; consumed by worker, critic, finalizer, and
  CLI renderers. The `used_safe_fallback` compatibility field is true for the
  deterministic clarification fallback after understanding failure.

Model I/O models in `src/prompt_orchestrator/domain/model_io.py`:

- `ModelMessage`: fields `role` (`system`, `user`, `assistant`) and `content`.
  Created by stages; consumed by providers and diagnostics.
- `ModelRequest`: fields `role`, `model_name`, `messages`, `temperature`,
  `max_output_tokens`, `timeout_seconds`, `request_kind`. Created by stages;
  consumed by `ModelClient.generate`.
- `TokenUsage`: fields `input_tokens`, `output_tokens`, `total_tokens`.
  Created by providers; consumed by draft/final metadata.
- `ModelResponse`: fields `text`, `model`, `finish_reason`, `usage`,
  `provider_metadata`. Created by providers; consumed by stages.

Result models in `src/prompt_orchestrator/domain/results.py`:

- `PromptPlan`: fields `strategy`, `worker_role`, `system_prompt`,
  `user_prompt`, `output_contract`, `quality_criteria`. Created by
  `build_worker_prompt_plan`; consumed by `plan` CLI and `run_worker_stage`.
  `worker_role` is derived from trusted strategy registry metadata.
- `DraftResponse`: fields `text`, `model_name`, `role`, `warnings`, `usage`.
  Created by worker/revision stages; consumed by critic/quality/finalizer.
- `CriticIssue`: fields `code`, `severity`, `message`, `criterion`. Created by
  critic model output; consumed by revision prompt and final quality metadata.
- `CriticResult`: fields `schema_version`, `passes`, `issues`,
  `violated_criteria`, `revision_recommended`, `revision_instruction`,
  `concise_summary`. Validator enforces schema version, pass/revision
  consistency, and revision instruction presence. Created by structured critic
  parsing; consumed by quality and revision stages.
- `QualityResult`: fields `status`, `critic_result`, `warnings`. Created by
  critic/quality stages; consumed by finalizer.
- `RoleModelNames`: fields `understanding`, `worker`, `critic`, `revision`.
  Created by finalizer from config role bindings; consumed by `FinalResponse`.
- `FinalResponse`: fields `status`, `text`, `clarification_question`,
  `strategy`, `roles`, `assumptions`, `warnings`, `critic_status`,
  `revision_performed`, `used_safe_fallback`, `trace`. Validator enforces
  status-specific shape. Created by finalizer; consumed by CLI JSON/text output
  and library callers. The `used_safe_fallback` field mirrors
  `ValidatedExecutionPlan.used_safe_fallback`.

Trace models:

- `TraceEvent` and `Trace` in `src/prompt_orchestrator/domain/trace.py`.
  Created by `TraceCollector`; consumed by final responses and CLI trace
  rendering. Trace details are bounded JSON-compatible maps.
- `LlmIoMessage`, `LlmIoCallRecord`, and `LlmIoTraceRecorder` in
  `src/prompt_orchestrator/stages/trace.py` are dataclasses for explicit
  diagnostic model I/O, not normal sanitized trace schemas.

Configuration schemas are documented in section 6.

## 6. Configuration system

Default config search is implemented by `find_config_path` in
`src/prompt_orchestrator/config/loader.py`:

```text
PROMPT_ORCHESTRATOR_CONFIG
  -> ./config.local.yaml
  -> ./config.yaml
  -> CONFIG_NOT_FOUND
```

Supported format:

- YAML loaded with `yaml.safe_load` in `load_config_from_path`.
- Root must be a mapping.
- Unknown keys are rejected by Pydantic config models.

Important configuration models in `src/prompt_orchestrator/config/models.py`:

- `PromptOrchestratorConfig`: top-level `version`, `providers`, `models`,
  `roles`, `runtime`, and non-serialized `path`.
- `OpenAICompatibleProviderConfig`: `type="openai_compatible"`, `base_url`,
  optional `api_key_env`, non-secret `default_headers`, `secret_headers`,
  `verify_tls`, resolved secret `api_key`.
- `MockProviderConfig`: `type="mock"`, `fixture_path`.
- `ModelConfig`: `provider`, `model`, `temperature`, `max_output_tokens`,
  `timeout_seconds`, `extra_body`, `metadata`.
- `RoleBindings`: required `understanding`, `worker`, `critic`, `revision`.
- `RuntimeConfig`: `structured_output_repair_attempts`,
  `transient_http_retries`, `enable_critic`, `strict_critic`,
  `enable_revision`, `max_revision_attempts`, `understanding_failure_mode`,
  `default_output_mode`, `strategy_overrides`, `trace`.
- `TraceConfig`: `enabled_by_default`.
- `StrategyOverride`: optional `enable_critic`, `enable_revision`.
- `SecretValue`: wraps resolved secret values and redacts `repr`/`str`; raw
  access is available only through `reveal()` for provider boundary code.

Environment-variable behavior:

- Only `api_key_env` and `secret_headers.*.env` names are stored in YAML.
- `OpenAICompatibleProviderConfig.resolve_api_key` reads the environment.
- `SecretHeaderConfig.resolve_value` reads secret header values from the
  environment.
- Missing non-empty required secrets fail during config validation.
- Local OpenAI-compatible endpoints can omit API keys by setting
  `api_key_env: null`.
- Secret values are excluded from serialized config and sanitized summaries.
- Known secret values are registered in `redaction.py` for trace and
  diagnostic redaction.

Role resolution:

```text
logical role -> named model -> provider adapter -> endpoint
worker -> local_general -> local_llama_server -> http://127.0.0.1:8080/v1
```

Implemented validation behavior:

- Provider/model names are constrained by `ConfigName`.
- Provider references in `ModelConfig.provider` must exist.
- Role bindings must reference existing named models.
- `version` must be `1`.
- Runtime repair/retry/revision counts are bounded to `0` or `1` in the MVP.
- `default_output_mode` accepts `text`, `markdown`, or `json`.
- `summarize_config` in `src/prompt_orchestrator/config/validation.py`
  returns provider names, model names, role bindings, and selected runtime
  settings without secrets.

Planned configuration features not implemented:

- Role fallback chains.
- Per-role retry policies separate from model settings.
- Provider capability metadata beyond free-form `ModelConfig.metadata`.
- Model availability checks.
- Context limits, concurrency limits, cost tiers enforced by policy, or
  automatic model selection.
- Service configuration, persistence configuration, retrieval/tool
  permissions, and multi-user/project configuration.

## 7. Model providers and clients

Common interface:

- `ModelClient` protocol in `src/prompt_orchestrator/clients/base.py` exposes
  `generate(request: ModelRequest) -> ModelResponse`, `close()`, `aclose()`,
  and context-manager hooks.
- Pipeline and stages depend on this interface, not HTTPX or provider payloads.

Implemented providers/clients:

- Provider identifier `mock`:
  - Config schema: `MockProviderConfig` in
    `src/prompt_orchestrator/config/models.py`.
  - Runtime clients: `MockModelClient`, `ScriptedModelClient`,
    `ScriptedResponse` in `src/prompt_orchestrator/clients/mock.py`.
  - Purpose: deterministic tests and examples.
  - Request format: provider-neutral `ModelRequest`.
  - Response handling: returns fixed text or ordered scripted text/JSON.
  - Structured-output support: scripts can return JSON text; parsing occurs in
    stages, not in the client.
  - Retry/timeout: none in mock client.
  - Error normalization: scripted steps can raise `ProviderError`; unexpected
    call order raises `AssertionError` for tests.

- Provider identifier `openai_compatible`:
  - Config schema: `OpenAICompatibleProviderConfig`.
  - Runtime client: `OpenAICompatibleModelClient` in
    `src/prompt_orchestrator/clients/openai_compatible.py`.
  - API style: OpenAI-compatible `/chat/completions`.
  - Request format: JSON with `model`, `messages`, `temperature`, `max_tokens`,
    plus `ModelConfig.extra_body`.
  - Headers: non-secret `default_headers`, `Authorization: Bearer ...` when
    `api_key` is resolved, and environment-backed `secret_headers`.
  - Response handling: reads first `choices[0].message.content`, optional
    `finish_reason`, token usage from `usage.prompt_tokens`,
    `usage.completion_tokens`, `usage.total_tokens`, and safe metadata
    `id`, `object`, `created`.
  - Structured-output support: no provider-native structured-output mode; the
    raw text is parsed by stages.
  - Retry behavior: retries timeouts, request errors, and HTTP 500/502/503/504
    up to `runtime.transient_http_retries`; does not retry 401/403.
  - Timeout behavior: uses `ModelRequest.timeout_seconds`.
  - Error normalization: maps auth to `ProviderAuthenticationError`, timeout
    to `ProviderTimeoutError`, invalid responses and HTTP failures to
    `ProviderError`.
  - Live purpose: local llama-server or compatible hosted endpoint.

- Diagnostic wrapper:
  - `DiagnosticModelClient` in `src/prompt_orchestrator/clients/diagnostic.py`
    wraps any `ModelClient` when `--show-llm-io` or `--save-llm-io` is used.
  - It records stage, role, resolved model, provider type/name, exact messages,
    raw response text, extracted JSON, validation errors, and provider errors
    through `LlmIoTraceRecorder`.

Client factory:

- `ClientFactory.create_for_role`, `create_client_for_role`,
  `RoutedModelClient`, and `create_pipeline_client` live in
  `src/prompt_orchestrator/clients/factory.py`.
- If a single mock provider backs all models and its fixture file exists,
  `_shared_scripted_client` returns one `ScriptedModelClient` so multi-stage
  scripts consume calls in order.
- Otherwise `create_pipeline_client` builds a `RoutedModelClient` with one
  role-specific client per `ModelRole`.
- `RoutedModelClient.close()` closes each unique underlying client once and is
  idempotent. `DiagnosticModelClient.close()` delegates to the wrapped client.
- CLI handlers close clients in `finally` blocks after successful commands and
  controlled errors. `PipelineRunner.close()` delegates to its client.

## 8. Role system

Currently recognized roles are defined by `ModelRole` in
`src/prompt_orchestrator/domain/enums.py`:

- `understanding`
- `worker`
- `critic`
- `revision`

Role bindings are configured by `RoleBindings` in
`src/prompt_orchestrator/config/models.py`. Each role maps to a named model.
Different roles can use different named models, and tests verify distinct
worker/revision models in `tests/test_worker_stage.py`,
`tests/test_critic_revision_stages.py`, and `tests/test_cli_commands.py`.

Resolution:

- `PromptOrchestratorConfig.resolve_role(role)` returns `ResolvedModel` with
  role, named model, model config, provider name, and provider config.
- `ClientFactory` uses the resolved provider to construct clients.
- `DiagnosticModelClient` uses `resolve_role` to record diagnostics.

Fallback behavior:

- There is no role fallback chain.
- If config references are invalid, config loading fails before a model call.
- Model-produced `ExecutionPlan` no longer accepts `worker_role`; unknown or
  malicious role strings are rejected as extra schema input.
- Worker role selection is derived from trusted `StrategyDefinition.worker_role`
  metadata. Every MVP strategy currently uses `ModelRole.WORKER`.

Hardcoded role locations:

- `RoleBindings` requires the four MVP roles.
- Stages resolve fixed roles: understanding stage uses
  `ModelRole.UNDERSTANDING`, worker uses `prompt_plan.worker_role`, critic uses
  `ModelRole.CRITIC`, revision uses `ModelRole.REVISION`.
- Specialist worker roles are not implemented.

## 9. Strategy system

Registered strategy identifiers are all `StrategyId` enum values in
`src/prompt_orchestrator/domain/enums.py`:

- `direct_answer`
- `concise_explanation`
- `step_by_step_explanation`
- `structured_analysis`
- `planning`
- `comparison`
- `decision_support`
- `brainstorming`
- `draft_generation`
- `rewrite_preserve_meaning`
- `summarization`
- `information_extraction`
- `structured_output`
- `creative_generation`
- `empathetic_guidance`
- `technical_assistance`
- `safety_redirect`

Registry implementation:

- `StrategyDefinition` dataclass in
  `src/prompt_orchestrator/strategies/definitions.py`.
- `STRATEGY_REGISTRY`, `get_strategy`, and `strategy_registry_summary` in
  `src/prompt_orchestrator/strategies/registry.py`.
- Registry is a `MappingProxyType`, so callers receive a read-only mapping.
- Each strategy maps to `strategies/<strategy_id>.md`.

Mapping from understanding output:

- Understanding model outputs `ExecutionPlan.strategy`.
- Pydantic validates enum membership.
- `evaluate_execution_plan_policy` checks the strategy is registered.
- Worker prompt builder calls `get_strategy(plan.strategy)`.

Worker role selection:

- `ExecutionPlan` does not include `worker_role`.
- `StrategyDefinition.worker_role` in
  `src/prompt_orchestrator/strategies/definitions.py` is trusted application
  metadata and defaults to `ModelRole.WORKER`.
- `build_worker_prompt_plan` copies the role from strategy metadata into
  `PromptPlan.worker_role`.

Critic requirements:

- `StrategyDefinition.critic_recommended` defaults true.
- `creative_generation` sets `critic_recommended=False`.
- `safety_redirect` sets `requires_caution=True`, which forces critic required.
- High risk or high-stakes plans force critic required.
- Runtime `strategy_overrides` can set `enable_critic`.

Output contracts:

- `StrategyDefinition.supported_output_modes` controls allowed modes.
- Most strategies support text and markdown.
- `structured_analysis`, `information_extraction`, and `structured_output`
  also support JSON.
- Caller output-mode override takes precedence when supported.

Understanding failure strategy:

- `_clarification_failure_plan` in `stages/understanding.py` uses
  `structured_analysis`, high ambiguity, high risk, and an
  `ask_clarification` decision. Worker, critic, and revision are skipped by
  finalization.

Conditionals still present:

- Strategy-specific execution is currently mostly prompt-template selection.
- Policy contains conditionals for output-mode correction, critic enforcement,
  and clarification checks.
- Quality flow has conditionals for critic skipped/failed and revision
  recommended.

## 10. Prompt system

Template loading/rendering:

- `load_template` in `src/prompt_orchestrator/prompts/loader.py` loads
  package-relative `.md` files from `prompt_orchestrator.templates`, rejecting
  absolute paths, `..`, non-`.md`, and missing templates.
- `render_template` in `src/prompt_orchestrator/prompts/renderer.py` validates
  placeholders against explicit allowed-variable sets and uses
  `string.Template`.

Understanding prompt:

- Template: `understanding.md`.
- Path: `src/prompt_orchestrator/templates/understanding.md`.
- Renderer: `_render_understanding_prompt` in
  `src/prompt_orchestrator/stages/understanding.py`.
- Variables: `UNDERSTANDING_VARIABLES` in `prompts/renderer.py`.
- Purpose: ask the understanding role to return exactly one `ExecutionPlan`
  JSON object and not answer the user task.
- Inputs: user request, caller context, requested or runtime-default output
  mode, strategy registry summary, clarification policy, exact schema contract.
- Schema contract: `execution_plan_schema_contract` in
  `src/prompt_orchestrator/prompts/schemas.py`, including
  `EXECUTION_PLAN_JSON_SKELETON`. The skeleton does not include
  `worker_role`.
- Protections: user prompt and caller context are placed in `<USER_REQUEST>`
  and `<CALLER_CONTEXT>` delimiters and described as untrusted data.
- Versioning: template says `Contract version: 1`; `ExecutionPlan` requires
  `schema_version=1`.

Understanding repair prompt:

- Built in `_render_repair_prompt` in
  `src/prompt_orchestrator/stages/understanding.py`.
- Not a separate template file.
- Includes validation errors, invalid response in `<INVALID_RESPONSE>`,
  exact `ExecutionPlan` skeleton/rules, user request/context delimiters, and
  explicit guidance for observed invalid shapes.
- Expected output: corrected `ExecutionPlan` JSON only.

Worker prompts:

- Templates: one file per strategy in
  `src/prompt_orchestrator/templates/strategies/*.md`.
- Renderer: `build_worker_prompt_plan` in `stages/worker.py`.
- Variables: `COMMON_WORKER_VARIABLES`.
- Purpose: turn a validated plan into a worker system prompt and user prompt.
- Expected model output: plain answer text, unless the `OutputContract` asks
  for a bounded mode such as JSON.
- Protections: system prompt instructs the worker to treat delimited user
  content as untrusted data; templates include `<USER_REQUEST>` and
  `<CALLER_CONTEXT>`.

Critic prompt:

- Template: `critic.md`.
- Path: `src/prompt_orchestrator/templates/critic.md`.
- Renderer: `_render_critic_prompt` in `stages/critic.py`.
- Variables: `CRITIC_VARIABLES`.
- Purpose: evaluate draft against original request and validated plan.
- Expected model output: one `CriticResult` JSON object.
- Protections: original request, context, execution plan, draft, and criteria
  are delimited in separate sections.
- Repair prompt: `_render_repair_prompt` in `stages/critic.py`; includes
  validation errors and invalid response, but currently uses only a top-level
  schema summary from `build_repair_request_data`, not an exact nested skeleton.

Revision prompt:

- Template: `revision.md`.
- Path: `src/prompt_orchestrator/templates/revision.md`.
- Renderer: `_render_revision_prompt` in `stages/revision.py`.
- Variables: `REVISION_VARIABLES`.
- Purpose: produce one complete revised answer from original request, plan,
  draft, critic issues, and revision instruction.
- Expected model output: complete revised answer only.
- Protections: all inputs are delimited; prompt says not to mention
  orchestration.

## 11. Structured-output parsing

Implemented files:

- `src/prompt_orchestrator/parsing/json_extract.py`
- `src/prompt_orchestrator/parsing/structured.py`

Behavior:

- `strip_markdown_json_fence` removes one enclosing plain or `json` Markdown
  code fence when it wraps the whole output.
- `extract_json_object_text` locates exactly one balanced top-level JSON
  object and rejects none or multiple objects.
- Brace matching accounts for quoted strings and escapes.
- `parse_json_object` parses the extracted object with `json.loads`, rejects
  non-object JSON, and never uses `eval`.
- `validate_structured_output` extracts JSON text, parses it, validates it
  against a supplied Pydantic model, and returns
  `StructuredValidationResult(value, raw_object)`.
- Pydantic validation errors are condensed into path/message diagnostics and
  raised as `StructuredOutputError(code="STRUCTURED_SCHEMA_INVALID")`.
- JSON extraction/validation annotates `LlmIoTraceRecorder` when explicit LLM
  I/O diagnostics are active.
- `RepairBudget` bounds repair attempts.
- `build_repair_request_data` returns schema name, invalid response,
  validation errors, and top-level schema summary for repair prompts.

Malformed-response behavior:

- No complete object: `STRUCTURED_JSON_NOT_FOUND`.
- Multiple objects: `STRUCTURED_JSON_AMBIGUOUS`.
- Parse error: `STRUCTURED_JSON_PARSE_ERROR`.
- Non-object JSON: `STRUCTURED_JSON_NOT_OBJECT`.
- Schema mismatch: `STRUCTURED_SCHEMA_INVALID`.

Unknown enum behavior:

- Unknown enum values are rejected by Pydantic during schema validation.

Relevant tests:

- `tests/test_structured_parsing.py`
- `tests/test_understanding_stage.py`
- `tests/test_critic_revision_stages.py`
- `tests/test_cli_commands.py`

## 12. Pipeline and state transitions

Pipeline entry points:

- Library: `PipelineRunner.understand`, `PipelineRunner.plan`, and
  `PipelineRunner.run` in `src/prompt_orchestrator/pipeline/runner.py`.
- CLI: `_handle_understand`, `_handle_plan`, and `_handle_run` in
  `src/prompt_orchestrator/cli.py`.

State machine:

- `PipelineState` and `PipelineStateMachine` live in
  `src/prompt_orchestrator/pipeline/state.py`.
- The state machine validates explicit transitions and records history.
- `PipelineRunner.run` uses the state machine.
- `PipelineRunner.plan` uses the state machine internally but does not expose
  state history in `PipelinePlanResult`.

Current state-transition diagram:

```text
new
  -> intake_complete
  -> understanding_complete
  -> plan_validated
       -> clarification_required -> finalized
       -> refused -> finalized
       -> worker_complete
            -> critic_skipped -> finalized
            -> critic_failed -> finalized | failed
            -> critic_complete
                 -> revision_complete -> finalized
                 -> revision_skipped -> finalized
                 -> revision_failed -> finalized
                 -> finalized
  -> failed -> finalized
```

Retry budgets and limits:

- Structured-output repair attempts: `RuntimeConfig.structured_output_repair_attempts`,
  bounded to 0 or 1.
- HTTP transient retries: `RuntimeConfig.transient_http_retries`, bounded to
  0 or 1.
- Revision attempts: `RuntimeConfig.max_revision_attempts`, bounded to 0 or 1.
- No critic/revision loop exists after revision.

Short-circuit conditions:

- Clarification/refusal stop before worker generation.
- Plan command stops after worker prompt planning.
- Critic disabled or not required skips critic.
- Revision disabled, max attempts 0, or no recommendation skips revision.

Completion states:

- `completed`
- `completed_with_warnings`
- `clarification_required`
- `refused`
- `failed`

Degraded-result behavior:

- Understanding structured-output failure returns clarification-required by
  default; no worker draft is generated.
- Non-strict critic failure returns worker draft with warning.
- Revision failure preserves original worker draft with warning.

Cancellation behavior:

- No cancellation API, signal handling, task IDs, or resumable state exists.

## 13. Interfaces

Stable user interfaces:

- `python -m prompt_orchestrator --help`
- `prompt-orchestrator --help` when installed and on `PATH`
- `python -m prompt_orchestrator config validate --config PATH`
- `python -m prompt_orchestrator understand [options] PROMPT`
- `python -m prompt_orchestrator plan [options] PROMPT`
- `python -m prompt_orchestrator run [options] PROMPT`

Runtime options for `understand`, `plan`, and `run`:

- positional `prompt`
- `--stdin`
- `--context TEXT`
- `--config PATH`
- `--output-mode text|markdown|json`
- `--json`
- `--trace`
- `--show-llm-io`
- `--save-llm-io PATH`
- `--debug`

Standard input behavior:

- `--stdin` reads all stdin.
- If a positional prompt is also supplied with `--stdin`, CLI prepends it plus
  a newline to stdin content.
- Empty normalized input fails with `INPUT_EMPTY`.

JSON output modes:

- `understand --json` prints the validated plan wrapper via
  `ValidatedExecutionPlan.model_dump(mode="json")`.
- `plan --json` prints a payload with `status`, optional `prompt_plan`,
  optional `validated_plan`, optional `final_response`, and optional `trace`.
- `run --json` prints `FinalResponse`.
- Controlled CLI errors with `--json` print `{"status":"failed","error":...}`.

Trace modes:

- `--trace` includes sanitized in-memory `Trace` in JSON or text summaries.
- `runtime.trace.enabled_by_default` also enables trace inclusion.
- `--show-llm-io` prints explicit model I/O diagnostics to stderr.
- `--save-llm-io PATH` writes JSONL model I/O diagnostics to a file.

Library-level APIs:

- `PipelineRunner` and result dataclasses in `pipeline/runner.py`.
- Stage functions exported from `stages/__init__.py`.
- Domain models exported from `domain/__init__.py`.
- Client factory functions exported from `clients/__init__.py`.
- Config loaders exported from `config/__init__.py`.

HTTP APIs:

- None implemented. HTTPX is used only as a client for model providers.

Current exit codes:

- `0`: success and non-failed final responses.
- `1`: unexpected internal error or final response status `failed`.
- `2`: `ConfigurationError`.
- `3`: `InputError`.
- `4`: `ProviderError`.
- `5`: other controlled `PromptOrchestratorError`.

Internal interfaces:

- Stage result dataclasses, state machine, prompt renderer, and parsing helpers
  are implementation interfaces but are tested directly and useful extension
  points.

## 14. Trace and observability

Sanitized trace:

- Implemented by `TraceCollector` in `src/prompt_orchestrator/stages/trace.py`.
- In-memory only; not persisted.
- Stores ordered `TraceEvent` objects with stage, event, status, duration,
  attempt, sanitized details, warning code, and error code.
- `_sanitize_details` redacts sensitive key names and exact known secret values
  registered from `api_key_env` and `secret_headers`.
- Pipeline trace currently records high-level events such as intake normalized,
  understanding model request/response, validation, policy evaluation, worker
  generation, quality review, finalization, and failures.
- Normal sanitized trace does not include full prompts or raw responses.

Explicit LLM I/O diagnostics:

- Implemented by `DiagnosticModelClient` and `LlmIoTraceRecorder`.
- Enabled only by `--show-llm-io` or `--save-llm-io`.
- Records exact request messages and raw response text, so user prompt content
  and model output are included by explicit opt-in.
- Also records extracted structured JSON and validation errors when parsing is
  attempted.
- Writes human-readable stderr output or JSONL file.
- Does not dump environment variables, API-key values, or resolved secret
  header values. Exact known secret values are redacted where practical.

Model and role selection records:

- Sanitized trace records model names in some stage events.
- Final response includes configured role-to-model names via `RoleModelNames`.
- LLM I/O diagnostics include resolved role, model, provider name, and
  provider type.

Token usage:

- `OpenAICompatibleModelClient` parses token usage into `TokenUsage`.
- Worker and revision `DraftResponse` preserve usage.
- Final response does not currently aggregate token usage.

Known observability gaps:

- No persistent event log.
- No trace levels.
- No model-call count summary.
- No prompt template version metadata beyond inline `Contract version: 1`.
- No structured metrics, health checks, or service logs.
- Prompt summary, full prompt trace, and configured user-content redaction
  settings are not implemented and are not accepted in public config.

## 15. Error handling and fallback behavior

Missing configuration:

- `find_config_path` raises `ConfigurationError(code="CONFIG_NOT_FOUND")`.
- CLI exits 2.
- No model call occurs.

Invalid configuration:

- YAML parse and Pydantic validation failures become `ConfigurationError`
  codes such as `CONFIG_YAML_INVALID` or `CONFIG_INVALID`.
- CLI exits 2.
- No model call occurs.

Unavailable endpoint or transport failure:

- `OpenAICompatibleModelClient.generate` maps request errors to
  `ProviderError(code="PROVIDER_REQUEST_FAILED")` and timeouts to
  `ProviderTimeoutError(code="PROVIDER_TIMEOUT")`.
- Transient retry is bounded by config.
- Worker provider failure fails the pipeline.
- Critic provider failure degrades or fails depending on `strict_critic`.
- Revision provider failure preserves original draft with warning.

Timeout:

- Same as provider timeout; uses `request.timeout_seconds`.

Malformed structured output:

- Understanding: repair once if budget allows; then clarification-required
  final response. Worker, critic, and revision are not called.
- Critic: repair once if budget allows; then degrade or fail depending on
  strict critic.
- Revision: not structured; empty output is a revision failure.

Schema failure:

- Same as malformed structured output, with `STRUCTURED_SCHEMA_INVALID`.

Unknown role:

- Config role references unknown models fail config validation.
- Model output cannot provide `worker_role`; extra role fields fail schema
  validation before policy.

Unknown strategy:

- Unknown enum value fails schema validation.
- Registered enum missing from supplied registry raises `PolicyError`.

Empty worker response:

- `run_worker_stage` raises `WorkerError(code="WORKER_EMPTY_RESPONSE")`.
- Pipeline returns failed final response; CLI `run` exits 1 for failed status.

Critic parse failure:

- One repair attempt if enabled.
- Non-strict mode returns completed-with-warnings and `critic_status=not_checked`.
- Strict mode fails with `CriticError(code="CRITIC_FAILED")`.

Revision failure:

- Empty revision output raises `RevisionError(code="REVISION_EMPTY_RESPONSE")`
  inside revision stage.
- `run_revision_stage` catches provider/revision errors and returns original
  draft plus warning.

Unexpected internal error:

- CLI prints `Error [UNEXPECTED_ERROR]: Unexpected internal error.` and exits 1.
- `--debug` prints a traceback.

## 16. Security and trust boundaries

Implemented protections:

- User prompt and caller context are treated as untrusted text in templates and
  delimited with `<USER_REQUEST>` and `<CALLER_CONTEXT>`.
- User input is never used as a prompt template name, provider name, endpoint,
  role binding, or schema.
- Prompt templates are package-controlled and loaded only through
  `load_template`.
- Template rendering uses explicit allowed-variable sets and fails on missing,
  unexpected, or disallowed placeholders.
- Model-produced `ExecutionPlan` and `CriticResult` are parsed as JSON data and
  Pydantic validated before use.
- Deterministic policy validates and can modify plan control fields before
  worker execution.
- Secrets are referenced by environment-variable name and resolved only in the
  config layer.
- `SecretValue` redacts normal string/repr output and config serialization.
- `SecretHeaderConfig` resolves environment-backed secret HTTP headers.
- Sensitive literal `default_headers` are rejected; secret headers must use
  `secret_headers`.
- Sanitized traces and explicit diagnostics redact sensitive key names and
  exact known secret values via `src/prompt_orchestrator/redaction.py`.
- OpenAI-compatible client uses HTTPX timeouts and does not include server
  error body text in `ProviderError`, avoiding reflected secret leakage from
  response bodies.
- Runtime has no tools, shell execution, browser access, file mutation by
  models, or arbitrary model-selected endpoints.

Protections not implemented or limited:

- No formal prompt-injection guarantee; protections are prompt-structure and
  validation based.
- No response body size limit beyond provider/client memory behavior and model
  output token configuration.
- No access-control system, user identity, project isolation, or audit log.
- No policy layer for future tools/retrieval because those features do not
  exist.
- `--show-llm-io` intentionally prints user prompts and raw model output; it is
  explicit opt-in. Known secret values are still redacted where practical.

## 17. Testing and quality gates

Framework and tooling:

- Test framework: pytest, configured in `pyproject.toml`.
- Default pytest excludes `live` tests with `addopts = "-ra -m 'not live'"`.
- Linting and formatting: Ruff.
- Type checking: mypy strict mode for `src` and `tests`.
- Coverage target documented in `TESTING.md`: at least 85% line coverage for
  `src/prompt_orchestrator`.

Exact commands documented by project:

```bash
pytest
pytest --cov=src/prompt_orchestrator --cov-report=term-missing --cov-fail-under=85
ruff check .
ruff format --check .
mypy src
python -m prompt_orchestrator --help
```

Optional live command:

```bash
PROMPT_ORCHESTRATOR_LIVE_CONFIG=examples/config.local-llama.yaml pytest -m live
```

Test directory structure:

- Tests are flat under `tests/`, not split into `unit/` and `integration/`
  directories.
- There is no `tests/fixtures/` directory in the verified tree; tests mostly
  build fixtures inline or use `examples/scripted-basic.yaml`.

Regression coverage includes:

- Public schema examples, enum failures, and consistency validators.
- Config search, validation, secret resolution/redaction, secret header
  handling, and CLI config validation.
- Mock/scripted client behavior and OpenAI-compatible HTTP payload/retry/error
  behavior using `httpx.MockTransport`.
- JSON extraction, Markdown fences, malformed/truncated/multiple objects,
  schema failures, and repair budgets.
- Strategy registry completeness and prompt-template invariants.
- Understanding prompt skeleton and repair prompt guidance for observed bad
  structured output.
- Worker prompt planning, role call, empty output, and gate blocking.
- Critic pass, repair, strict/non-strict failure, revision, and revision
  failure.
- Pipeline outcomes, state transitions, sanitized trace, clarification,
  refusal, degraded critic results, and understanding-failure clarification.
- CLI text/JSON/stdin/trace/debug/LLM I/O diagnostics.
- Client lifecycle close behavior for routed clients, mock/scripted clients,
  and CLI success/error paths.
- Scripted example commands.
- Optional live run.

Known test gaps:

- No persisted-state tests because persistence is not implemented.
- No service/API tests because no HTTP service exists.
- No cancellation/concurrency tests.
- No automated documentation-source consistency test, by design.
- No live tests run by default.

## 18. Current roadmap status

Phase 0 - MVP baseline: implemented. The code implements the single-request
orchestration baseline, CLI, mock/scripted clients, OpenAI-compatible provider,
structured validation, clarification gate, strategy registry, worker
generation, critic, one revision, final response, in-memory trace, explicit
LLM I/O diagnostics, client lifecycle cleanup, and current MVP secret
redaction. Relevant files include `pipeline/runner.py`, `stages/*.py`,
`clients/*.py`, `redaction.py`, and `cli.py`.

Phase 1 - Multi-model orchestration: partially implemented. Completed:
logical roles can map to different named models and providers through
`RoleBindings`, `PromptOrchestratorConfig.resolve_role`, `ClientFactory`, and
`RoutedModelClient`. Selected role/model appears in final response roles,
sanitized trace details in some stages, and diagnostic LLM I/O. Missing:
expanded roles such as planner/summarizer/fallback, model registry with
capabilities, role fallback chains, availability checks, role-specific retry
policies, provider capability metadata, and controlled unavailable-model
fallback behavior.

Phase 2 - Strategy-specific execution: partially implemented. Completed:
static `StrategyId` enum, `STRATEGY_REGISTRY`, one template per strategy,
strategy validation, output-mode support checks, default quality criteria, and
critic recommendation/caution flags. Missing: substantially different
strategy-specific execution flows, planner roles, strategy-specific critic
rubrics beyond criteria, strategy version metadata, decomposition permissions,
and removal of all strategy behavior conditionals.

Phase 3 - Multi-step planning and execution: not started. No task plan schema,
step schema, step execution loop, step state, replan behavior, pause/resume, or
final synthesis from step outputs exists.

Phase 4 - Persistent task state and observability: not started. No
`.orchestrator/tasks` storage, task IDs, state snapshots, event JSONL logs,
inspect/resume/events CLI, persistence schema, or migration policy exists.
Current trace is in-memory only.

Phase 5 - Evaluation and regression framework: partially implemented.
Completed: an evaluation package (`src/prompt_orchestrator/evaluation/`) with a
YAML corpus loader and `EvalCase`/`EvalChecks` schema, deterministic model-free
checks (`must_include`, `must_avoid`, length, expected status), an orchestrated
vs single-call baseline comparison, per-arm token/latency cost accounting via
`MeteringModelClient`, an opt-in pairwise model judge, an `EvalReport`, and a
`prompt-orchestrator eval` CLI command (`--corpus`, `--judge`, `--no-baseline`,
`--json`). Missing: rubric-scored regressions by category over time,
baseline-run comparison beyond single-call, evaluation-set versioning and report
persistence, latency-tier and local-vs-hosted comparisons, and prompt-template
version tracking in reports.

Phase 6 - Coding-harness planning and review mode: not started. No
`coding-plan`, `coding-review`, or `coding-repair` CLI commands or coding-plan
schemas exist.

Phase 7 - API and service mode: not started. No HTTP server, endpoints, task
queue, async execution, health checks, or network service schemas exist.

Phase 8 - Coding-harness compatibility and OpenAI-compatible facade: not
started. No `/v1/chat/completions`, `/v1/responses`, streaming, tool-call
compatibility, or harness-native mode exists.

Phase 9 - RAG and context acquisition: intentionally deferred. No retrieval
subsystem, source registry, indexes, context packets, citations, or retrieval
trace exists.

Phase 10 - Controlled tool execution: intentionally deferred. No tool registry,
tool schemas, model tool requests, approval policy, or tool execution adapters
exist.

Phase 11 - Automatic model selection and escalation: not started. No automatic
selection policy, dry-run selection, hosted escalation approval, cost budgets,
or evaluation-informed routing exists.

Phase 12 - Multi-user and shared deployment: not started. No authentication,
user/project identity, quotas, scheduling, isolation, or shared model pools
exist.

Phase 13 - Production hardening: not started beyond MVP quality gates and
basic redaction/retry tests. No metrics, circuit breakers, structured logging,
rate limiting, graceful shutdown, backups, or load tests exist.

## 19. Known limitations and technical debt

- Component: configuration/model routing.
  Impact: no fallback chain if a role model is unavailable.
  File/symbol: `RoleBindings`, `PromptOrchestratorConfig.resolve_role`,
  `ClientFactory.create_for_role`.
  Likely roadmap phase: Phase 1.
  Blocks later work: blocks robust multi-model routing.

- Component: strategy execution.
  Impact: strategies change prompt text and metadata but not separate execution
  algorithms.
  File/symbol: `STRATEGY_REGISTRY`, `build_worker_prompt_plan`.
  Likely roadmap phase: Phase 2.
  Blocks later work: partially blocks strategy-specific execution and planning.

- Component: critic repair prompt.
  Impact: critic repair uses a top-level schema summary, unlike the exact
  understanding skeleton.
  File/symbol: `_render_repair_prompt` in `stages/critic.py`,
  `_schema_shape_summary` in `parsing/structured.py`.
  Likely roadmap phase: Phase 2 or hardening.
  Blocks later work: does not block but may reduce structured-output reliability.

- Component: pipeline persistence.
  Impact: cannot inspect, resume, or reproduce tasks after process exit.
  File/symbol: `PipelineRunner`, `TraceCollector`.
  Likely roadmap phase: Phase 4.
  Blocks later work: blocks multi-step resumability and service mode.

- Component: cancellation/concurrency.
  Impact: long model calls cannot be cancelled through a first-class API.
  File/symbol: `PipelineRunner.run`, `OpenAICompatibleModelClient.generate`.
  Likely roadmap phase: Phase 7.
  Blocks later work: blocks service queue/cancel endpoints.

- Component: final response usage accounting.
  Status: addressed. `MeteringModelClient` aggregates per-call token usage and
  latency into `RunUsage`; `run` attaches it to `FinalResponse.usage` (shown in
  `--json`, and under `--trace` in text mode) and the evaluation harness records
  it per arm. Remaining: usage is captured at the client boundary rather than
  inside each stage result, and provider cost/pricing is not modeled.
  File/symbol: `clients/metering.py`, `domain/usage.py`, `FinalResponse.usage`.
  Likely roadmap phase: Phase 4 or 5.

- Component: user metadata.
  Impact: `PromptRequest.metadata` exists but is not injected into prompts or
  used in policy.
  File/symbol: `PromptRequest`, `normalize_input`.
  Likely roadmap phase: Phase 4 or 7.
  Blocks later work: may need design before task state/API.

- Component: roadmap tracking.
  Impact: `ROADMAP.md` existed as untracked at verification, so planners should
  confirm it is committed before relying on it across branches.
  File/symbol: `ROADMAP.md`.
  Likely roadmap phase: documentation governance.
  Blocks later work: can confuse branch-based planning if not committed.

## 20. Architectural invariants

Supported by current code and accepted docs:

- Provider-specific behavior remains behind the `ModelClient` interface.
- Pipeline and stages request logical roles, not provider URLs.
- Configuration maps role -> named model -> provider.
- Model outputs used for control flow are schema validated before use.
- Deterministic policy validates or corrects model-selected strategy, role,
  output mode, critic requirement, and clarification shape.
- Unknown strategies and roles cannot execute unchecked.
- Structured-output repair, HTTP retries, and revision are bounded.
- The MVP has at most one revision pass and no second critic loop after
  revision.
- User prompts and caller context are delimited in model prompts.
- Prompt templates are package-controlled and not selected by user input.
- Tests must run without live models by default.
- CLI rendering is separate from core `PipelineRunner`.
- Secrets remain outside committed config files and are referenced by
  environment-variable name.
- Normal trace data is sanitized and in-memory only.
- Explicit raw LLM I/O diagnostics are opt-in.
- No RAG, tools, memory, database, service mode, web UI, streaming, or
  automatic API escalation exists in the MVP.

## 21. Extension points for the next phases

Multi-model orchestration:

- Current interface: `RoleBindings`, `PromptOrchestratorConfig.resolve_role`,
  `ClientFactory`, `RoutedModelClient`, `ModelRequest.role`.
- Likely modification: add role profiles, model registry/capabilities,
  fallback chains, availability checks, and role-specific retry policies.
- Coupling/risk: `RoleBindings` currently requires exactly four role fields;
  policy forces worker role to `worker`.
- Missing abstraction: first-class model registry and fallback policy.

Strategy-specific execution:

- Current interface: `StrategyDefinition`, `STRATEGY_REGISTRY`,
  strategy templates, `build_worker_prompt_plan`.
- Likely modification: add strategy execution descriptors, critic rubrics,
  planner/decomposition flags, prompt-template versions, and strategy-specific
  stage hooks.
- Coupling/risk: core runner assumes one worker path.
- Missing abstraction: strategy execution plan beyond template metadata.

Multi-step planning:

- Current interface: `ExecutionPlan`, `PipelineStateMachine`, `PipelineRunner`.
- Likely modification: introduce task-plan and step schemas, step runner,
  bounded step budgets, step result retention, and final synthesis.
- Coupling/risk: current `ExecutionPlan` describes one worker action only.
- Missing abstraction: persistent or in-memory task state model.

Persistent task state:

- Current interface: `Trace`, `FinalResponse`, `PipelineRunResult`.
- Likely modification: add task IDs, serializable state snapshots, event JSONL,
  config snapshots, output references, and inspect/resume commands.
- Coupling/risk: current stages return in-memory Pydantic/dataclass results.
- Missing abstraction: storage adapter and versioned task-state schema.

Evaluation:

- Current interface: pytest suite, `ScriptedModelClient`, `PipelineRunner`.
- Likely modification: add evaluation case schemas, runner CLI, reports, and
  deterministic plus optional model-judged scoring.
- Coupling/risk: no current stable evaluation artifact schema.
- Missing abstraction: evaluation corpus loader and report model.

Coding-harness planning mode:

- Current interface: strategy registry and CLI command parser.
- Likely modification: add coding-plan schemas, prompt templates, and CLI
  commands that produce Markdown/JSON handoff artifacts.
- Coupling/risk: current orchestrator is task-general and does not inspect
  repositories.
- Missing abstraction: repository-context request and harness-handoff schemas.

API service:

- Current interface: `PipelineRunner` independent of CLI presentation.
- Likely modification: wrap runner in web/API layer, async task management,
  queue, cancellation, health/readiness, and shared config loading.
- Coupling/risk: provider clients are synchronous; lifecycle management is
  minimal.
- Missing abstraction: task queue, cancellation token, storage, service schemas.

Harness compatibility:

- Current interface: `ModelRequest`/`ModelResponse` resemble chat messages but
  omit tool calls and streaming events.
- Likely modification: protocol-specific request/response schemas and
  harness-native finalization.
- Coupling/risk: normal critic/finalizer can corrupt tool-call protocols if
  reused blindly.
- Missing abstraction: protocol adapter and compatibility mode.

RAG:

- Current interface: `PromptRequest.context` and worker prompt context
  delimiter.
- Likely modification: add context request schema, retrieval stage, source
  registry, context packet, provenance/citations, and critic checks for context
  use.
- Coupling/risk: no current source permissions or storage.
- Missing abstraction: retrieval provider and context packet schema.

Tools:

- Current interface: none in runtime.
- Likely modification: tool request/result schemas, registry, permissions,
  approval flow, budgets, and verifier.
- Coupling/risk: major security model change.
- Missing abstraction: policy-controlled capability system.

Automatic escalation:

- Current interface: role-to-model config and free-form model metadata.
- Likely modification: selection policy, local-only/hosted approval settings,
  cost/latency/quality metadata, and trace reasons.
- Coupling/risk: current config has no approval or budget model.
- Missing abstraction: model-selection policy and audit trail.

Multi-user operation:

- Current interface: none beyond local single-user CLI.
- Likely modification: auth, user/project identity, isolated config/state,
  quotas, audit logs, scheduler.
- Coupling/risk: current configs and traces are process-local and not scoped by
  user/project.
- Missing abstraction: identity, authorization, and multi-tenant storage.

## 22. Planner handoff checklist

Before producing an implementation plan for a roadmap phase, verify:

- Target roadmap phase and explicit scope.
- Current phase status in `ROADMAP.md` and this document.
- Reusable components, especially domain models, config models, clients,
  stages, prompts, strategies, and tests.
- Missing abstractions that the phase requires.
- Schemas to extend or introduce.
- Public CLI/library interfaces that must remain compatible.
- Trace, diagnostics, and error behavior that must stay stable.
- Tests to add or update, including failure paths and no-network scripted
  cases.
- Configuration changes and migration/default behavior.
- Documentation changes, especially `README.md`, `PROJECT_STATE.md`,
  `CONFIGURATION.md`, `DATA_MODELS.md`, and `PROMPT_CONTRACTS.md`.
- Any migration requirements for existing config examples or JSON outputs.
- Explicit non-goals that still apply, especially RAG/tools/service/memory
  boundaries unless the selected roadmap phase intentionally changes them.
