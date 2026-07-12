# Project Decisions

These decisions are fixed for the MVP so Codex does not need to choose foundational technologies or behaviors while implementing milestones.

## Product identity

- Project name: **Prompt Orchestrator**.
- Python package: `prompt_orchestrator`.
- CLI command: `prompt-orchestrator`.
- Primary interface: local CLI.
- Configuration format: YAML.

## Runtime pipeline

The canonical pipeline is:

```text
PromptRequest
  → IntakeResult
  → Understanding model
  → Parsed and validated ExecutionPlan
  → Deterministic policy evaluation
  → Clarification response OR worker execution
  → Critic review
  → Optional one-pass revision
  → FinalResponse
```

## Model roles

The MVP has four logical roles:

- `understanding`
- `worker`
- `critic`
- `revision`

All four roles may map to one configured model. They may also map to different local or hosted endpoints.

The runtime never chooses an unconfigured model name directly. It chooses a role or uses the role specified by a validated execution plan.

## Providers

The MVP implements two provider types:

- `mock`
- `openai_compatible`

`openai_compatible` targets an OpenAI-compatible chat-completions endpoint. This is suitable for local `llama-server` deployments and compatible hosted services.

Native OpenAI, Anthropic, Google, or other provider adapters are future work. They must be addable through the same `ModelClient` abstraction.

## Python and libraries

- Python: 3.12+
- packaging/build metadata: `pyproject.toml`
- validation and domain models: Pydantic v2
- YAML: PyYAML
- HTTP: HTTPX
- CLI: `argparse`
- prompt rendering: `string.Template`
- tests: pytest
- lint/format: Ruff
- type checking: mypy

## Understanding behavior

- Understanding is model-driven, not primarily keyword-driven.
- The understanding model returns a structured `ExecutionPlan`.
- Deterministic code validates schemas, enums, registered strategies, role mappings, risk constraints, and retry limits.
- A small deterministic fallback plan exists only for controlled failure handling; it is not the normal classifier.

## Clarification behavior

Ask a follow-up only when at least one of these is true:

- required input is absent;
- plausible interpretations are materially incompatible;
- a wrong assumption would make the answer unusable;
- safety depends on missing information.

Otherwise, proceed with explicit assumptions captured in the plan.

The MVP returns a clarification question and stops. It does not maintain a persistent conversation session. The caller submits the answer and relevant prior context in a new request.

## Critic and revision behavior

- Critic review is enabled by default.
- The critic evaluates the worker draft against the original request, execution plan, output contract, constraints, and quality criteria.
- The critic returns structured JSON.
- At most one revision pass is allowed.
- The revision model receives a concise revision instruction, not hidden critic reasoning.
- A revision is reviewed only by deterministic checks; there is no second critic call in the MVP.

## Failure defaults

- Understanding structured-output failure: one structured-output repair retry, then controlled failure or deterministic fallback according to configuration.
- Worker request failure: one transport retry for transient network failures; no content retry by default.
- Critic failure: return the worker draft marked `not_checked` unless strict critic mode is enabled.
- Revision failure: return the original worker draft plus a warning.
- No stage may loop indefinitely.

## Trace behavior

- Trace is in memory for one CLI run.
- Trace is not persisted by the MVP.
- Default output shows only the final answer or clarification.
- `--trace` displays stage summaries and sanitized metadata.
- `--json` returns structured result data.
- Full prompts may be shown only with an explicit debug flag and must redact secrets.

## Scope exclusions

No RAG, tools, memory, database, service API, web UI, or multi-user support in the MVP.
