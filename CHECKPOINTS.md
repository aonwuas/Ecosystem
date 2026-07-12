# Implementation Checkpoints

Implement checkpoints in order. Each checkpoint includes prerequisites, required work, acceptance criteria, and explicit exclusions.

## Milestone 1 — Repository scaffold and developer tooling

### Goal

Create an installable, testable Python project with the documented package and CLI names.

### Implement

- `pyproject.toml` for Python 3.12+.
- `src/prompt_orchestrator/` package.
- `__init__.py`, `__main__.py`, and minimal `cli.py`.
- `prompt-orchestrator` console entry point.
- runtime/dev dependency groups matching project decisions.
- Ruff, mypy, and pytest configuration.
- smoke tests for import, module invocation, and CLI help.
- retain and reference all specification documents.

### Acceptance

- editable install succeeds;
- `prompt-orchestrator --help` succeeds;
- `python -m prompt_orchestrator --help` succeeds;
- pytest, Ruff, formatting check, and mypy pass for scaffold.

### Do not implement

Domain schemas, config loading, model clients, prompts, or pipeline logic.

---

## Milestone 2 — Canonical domain models and enums

### Goal

Implement Pydantic models and enums from `DATA_MODELS.md`.

### Implement

- request/intake models;
- understanding, clarification, output contract, and execution-plan models;
- provider-neutral model request/response models;
- draft, critic, quality, final-response, and trace models;
- strict field validation, bounds, consistency validators, JSON serialization;
- unit tests with valid/invalid examples.

### Acceptance

- documented JSON examples validate;
- unknown enum values fail clearly;
- clarification and critic consistency rules are enforced;
- secret-bearing values are not part of domain models.

### Do not implement

Config loading, model calls, parsing raw model text, or pipeline stages.

---

## Milestone 3 — YAML configuration and role resolution

### Goal

Load and validate providers, named models, role bindings, and runtime policy.

### Implement

- discriminated provider config for `mock` and `openai_compatible`;
- named model config;
- all four role bindings;
- runtime retry/critic/revision/trace settings;
- environment-variable secret resolution with redaction;
- config search order;
- role → model → provider resolver;
- `config validate` CLI subcommand;
- sanitized config summary;
- tests for valid and invalid configurations.

### Acceptance

- `config.example.yaml` validates;
- missing provider/model/role references fail before network use;
- absent optional local API key works;
- required missing environment key fails without exposing values;
- role resolution is independently testable.

### Do not implement

HTTP model calls or pipeline stages.

---

## Milestone 4 — Model client abstraction and provider adapters

### Goal

Provide provider-neutral generation through mock and OpenAI-compatible clients.

### Implement

- `ModelClient` protocol/abstract interface;
- client factory;
- `MockModelClient` and `ScriptedModelClient`;
- OpenAI-compatible chat-completions client using HTTPX;
- request payload mapping;
- response/usage parsing;
- timeout and transient retry behavior;
- provider exception mapping and sanitization;
- HTTP mock tests.

### Acceptance

- no pipeline code knows URLs or HTTP payloads;
- scripted client verifies call order;
- local endpoint may omit API key;
- transport retry is bounded;
- provider errors do not expose secrets.

### Do not implement

Understanding prompts, critic prompts, or full pipeline.

---

## Milestone 5 — Structured-output extraction and validation

### Goal

Robustly convert model text into validated understanding and critic objects.

### Implement

- optional Markdown-fence removal;
- extraction of one top-level JSON object from limited surrounding prose;
- JSON parse errors with paths/context;
- Pydantic validation integration;
- structured-output repair request data;
- one-repair budget helper;
- tests for valid, fenced, noisy, malformed, truncated, missing-field, and extra-field outputs.

### Acceptance

- valid JSON is parsed directly;
- common fenced JSON is accepted;
- ambiguous/multiple top-level objects are rejected;
- invalid schemas produce concise repair diagnostics;
- no use of `eval` or permissive code execution.

### Do not implement

Actual repair model call or orchestration.

---

## Milestone 6 — Strategy registry and prompt-template system

### Goal

Define the bounded strategy set and render package-controlled prompts.

### Implement

- static strategy definitions for every MVP strategy;
- metadata for supported output modes, default quality criteria, and critic recommendation;
- package templates for understanding, worker strategies, critic, and revision;
- template loader restricted to package paths;
- `string.Template` renderer with allowed variables and missing-variable errors;
- stable user/context delimiters;
- prompt structural tests.

### Acceptance

- every registered strategy has one worker template;
- unknown strategy/template is rejected;
- user input cannot select a path;
- rendered prompts include required contracts and delimiters;
- no template requests hidden chain-of-thought.

### Do not implement

Model calls or pipeline stages.

---

## Milestone 7 — Intake and understanding stage

### Goal

Accept user input and obtain a validated model-produced execution plan.

### Implement

- intake normalization and empty-input validation;
- understanding prompt construction;
- understanding role resolution and call;
- structured parsing and validation;
- one structured-output repair call;
- safe fallback/error behavior from config;
- trace events for attempts and fallback;
- unit/integration tests using scripted clients.

### Acceptance

- a valid execution plan is returned;
- invalid first output can be repaired once;
- invalid repair follows configured failure mode;
- fallback is visibly marked;
- understanding stage does not answer the user's task.

### Do not implement

Worker, critic, revision, or full CLI run.

---

## Milestone 8 — Deterministic execution-plan policy and clarification gate

### Goal

Constrain model-produced control decisions before execution.

### Implement

- strategy and role registration checks;
- caller output-mode override handling;
- clarification consistency and policy;
- high-risk critic enforcement;
- bounded list/string normalization and deduplication;
- policy change/warning recording;
- proceed, clarification, and refusal outcomes;
- tests for policy corrections and rejections.

### Acceptance

- unregistered strategy or role cannot execute;
- model cannot disable required policy;
- clarification produces one focused question;
- a valid proceed plan remains semantically intact;
- all modifications appear in `policy_changes`.

### Do not implement

Worker or critic model calls.

---

## Milestone 9 — Worker prompt planning and generation stage

### Goal

Turn a validated execution plan into a worker prompt and draft answer.

### Implement

- `PromptPlan` builder;
- strategy-template selection;
- output contract and constraints insertion;
- worker role resolution;
- worker model call;
- empty-output handling;
- `plan` operation that returns prompt plan without calling worker;
- tests for representative strategies and caller context.

### Acceptance

- worker receives the correct strategy prompt;
- user content remains delimited;
- `plan` performs no worker call;
- worker result becomes a valid `DraftResponse`;
- clarification/refusal plans never call worker.

### Do not implement

Critic or revision.

---

## Milestone 10 — Critic and one-pass revision stages

### Goal

Evaluate the draft and optionally revise it once.

### Implement

- critic prompt construction and role call;
- critic structured parsing, repair, and consistency validation;
- strict/non-strict critic failure behavior;
- revision decision;
- revision prompt and role call;
- one-pass revision budget enforcement;
- deterministic final checks on revised text;
- preservation of original draft on revision failure;
- comprehensive scripted integration tests.

### Acceptance

- critic pass returns original draft;
- critic revision recommendation can produce revised draft;
- no second critic/revision loop occurs;
- critic failure degrades or fails according to config;
- revision failure preserves original answer with warning.

---

## Milestone 11 — Pipeline runner, state machine, finalizer, and trace

### Goal

Connect all stages into one application service independent of CLI presentation.

### Implement

- explicit pipeline state model and legal transitions;
- `PipelineRunner` operations: understand, plan, run;
- final response construction for completed, clarification, refusal, degraded, and failed paths;
- in-memory trace collector with timing and attempts;
- secret redaction and prompt-summary behavior;
- deterministic final checks;
- end-to-end scripted tests.

### Acceptance

- each major outcome returns a valid `FinalResponse`;
- illegal state transitions fail in tests;
- trace is optional and sanitized;
- pipeline API contains no CLI-specific printing;
- every loop/retry is bounded.

---

## Milestone 12 — Complete CLI and output rendering

### Goal

Expose the MVP through a usable command line.

### Implement

- commands: `config validate`, `understand`, `plan`, `run`;
- prompt argument and `--stdin` support;
- optional context input;
- `--config`, `--json`, `--trace`, and debug controls defined by specs;
- clean text renderer;
- structured JSON renderer;
- stable exit codes and concise errors;
- CLI tests.

### Acceptance

- documented README commands work;
- default run prints only user-facing result;
- clarification prints the question;
- JSON output is valid and contains status metadata;
- trace does not reveal secrets;
- stack traces require explicit debug mode.

---

## Milestone 13 — Examples, optional live smoke test, and documentation synchronization

### Goal

Make the completed MVP understandable and easy to validate with local models.

### Implement

- example scripted model fixtures;
- example local llama-server configuration;
- examples for all major CLI operations;
- optional `live` pytest marker/smoke test;
- README installation, configuration, usage, troubleshooting, and architecture overview;
- ensure all specification docs match implementation.

### Acceptance

- a new user can configure one local model for all roles;
- examples run with scripted clients without network;
- live test is opt-in;
- no doc claims unimplemented features.

---

## Milestone 14 — Hardening and MVP completion audit

### Goal

Finish the MVP without adding scope.

### Implement

- run and fix complete quality gates;
- achieve testing target with meaningful tests;
- audit secret redaction, retry limits, trace output, and schema strictness;
- audit Windows/Linux path and line-ending behavior;
- remove dead code and accidental future-feature stubs;
- verify package metadata and version;
- produce an MVP completion checklist in README or release notes section.

### Acceptance

- `pytest` passes;
- `ruff check .` passes;
- `ruff format --check .` passes;
- `mypy src` passes;
- coverage target is met;
- config example validates;
- full scripted pipeline passes;
- prohibited features are absent;
- repository is ready for manual local-model testing.
