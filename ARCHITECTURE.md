# Architecture

## 1. Architectural style

Prompt Orchestrator is a synchronous, CLI-first pipeline composed of explicit stages. The architecture favors small interfaces, immutable validated data, and deterministic policy around model-produced decisions.

The MVP is not an autonomous agent framework. Models generate text and structured plans; application code controls all stage transitions.

## 2. System context

```text
Human or calling script
        │
        ▼
Prompt Orchestrator CLI
        │
        ├── YAML configuration
        ├── environment variables for secrets
        └── configured model endpoints
                ├── local llama-server
                └── future hosted OpenAI-compatible API
```

## 3. Canonical pipeline

```text
PromptRequest
    │
    ▼
IntakeStage
    │ IntakeResult
    ▼
UnderstandingStage ──calls──> understanding role
    │ raw structured response
    ▼
StructuredOutputParser
    │ candidate ExecutionPlan
    ▼
ExecutionPlanValidator + PolicyEngine
    │ ValidatedExecutionPlan
    ├──────── clarification/refusal ───────> Finalizer
    │
    ▼
StrategyRegistry + PromptBuilder
    │ WorkerPrompt
    ▼
WorkerStage ──calls──> worker role
    │ DraftResponse
    ▼
CriticStage ──calls──> critic role
    │ CriticResult
    ├──────── pass/no revision ────────────> Finalizer
    │
    ▼
RevisionStage ──calls once──> revision role
    │ RevisedDraft
    ▼
DeterministicFinalChecks
    │
    ▼
Finalizer
    │ FinalResponse + optional Trace
    ▼
CLI renderer
```

## 4. Proposed repository layout

```text
.
├── AGENTS.md
├── ARCHITECTURE.md
├── CHECKPOINTS.md
├── CODEX_INSTRUCTIONS.md
├── CONFIGURATION.md
├── DATA_MODELS.md
├── DEVELOPMENT.md
├── ERROR_HANDLING.md
├── MVP.md
├── PROJECT_DECISIONS.md
├── PROMPT_CONTRACTS.md
├── README.md
├── SECURITY.md
├── TESTING.md
├── config.example.yaml
├── pyproject.toml
├── src/
│   └── prompt_orchestrator/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── exceptions.py
│       ├── config/
│       │   ├── loader.py
│       │   ├── models.py
│       │   └── validation.py
│       ├── domain/
│       │   ├── enums.py
│       │   ├── execution_plan.py
│       │   ├── requests.py
│       │   ├── results.py
│       │   └── trace.py
│       ├── clients/
│       │   ├── base.py
│       │   ├── factory.py
│       │   ├── mock.py
│       │   └── openai_compatible.py
│       ├── parsing/
│       │   ├── json_extract.py
│       │   └── structured.py
│       ├── policy/
│       │   ├── execution_plan.py
│       │   └── safety.py
│       ├── prompts/
│       │   ├── loader.py
│       │   └── renderer.py
│       ├── strategies/
│       │   ├── definitions.py
│       │   └── registry.py
│       ├── stages/
│       │   ├── intake.py
│       │   ├── understanding.py
│       │   ├── worker.py
│       │   ├── critic.py
│       │   ├── revision.py
│       │   └── finalizer.py
│       ├── pipeline/
│       │   ├── runner.py
│       │   └── state.py
│       └── templates/
│           ├── understanding.md
│           ├── critic.md
│           ├── revision.md
│           └── strategies/
│               ├── direct_answer.md
│               └── ...
└── tests/
    ├── fixtures/
    ├── unit/
    └── integration/
```

Codex may adjust filenames modestly when tests or packaging benefit, but component boundaries must remain recognizable.

## 5. Component responsibilities

### 5.1 CLI

Responsible for:

- argument parsing;
- reading prompt/context from arguments or stdin;
- loading configuration;
- invoking pipeline operations;
- rendering clean text, JSON, or trace output;
- translating domain exceptions into stable exit codes.

The CLI contains no provider-specific logic and no orchestration policy.

### 5.2 Configuration layer

Responsible for:

- loading YAML;
- resolving environment-variable references;
- validating providers, models, and role bindings;
- producing immutable runtime settings;
- preventing model calls when config is invalid.

### 5.3 ModelClient interface

Conceptual interface:

```text
generate(request: ModelRequest) -> ModelResponse
```

A model request contains normalized messages, sampling parameters, output limits, timeout settings, and optional structured-output hints.

The interface must not expose HTTPX types to pipeline code.

### 5.4 Client factory

Constructs one client per provider configuration and resolves a logical role through:

```text
role → named model → provider → client
```

### 5.5 IntakeStage

Normalizes line endings and surrounding whitespace, validates presence of a prompt, preserves supplied context, and creates `PromptRequest`/`IntakeResult` data.

It does not interpret user intent.

### 5.6 UnderstandingStage

Builds the understanding prompt, calls the configured role, parses structured output, and requests one repair attempt when parsing fails.

It does not execute the model-selected plan directly.

### 5.7 ExecutionPlanValidator

Validates the plan against `DATA_MODELS.md` and deterministic policy:

- known enums;
- known strategy ID;
- available role;
- internal consistency;
- supported output contract;
- bounded list/string sizes;
- required caution for sensitive categories;
- clarification rules.

It returns a validated plan, a policy-modified plan with recorded changes, or a controlled failure/fallback.

### 5.8 StrategyRegistry

A static application registry maps strategy IDs to:

- prompt-template path;
- description;
- supported output modes;
- default quality criteria;
- whether empathy/caution language is required;
- whether a critic is recommended.

Models cannot define new strategy IDs at runtime.

### 5.9 PromptBuilder

Creates worker prompts from validated data. It uses stable delimiters and escapes/rejects missing placeholders. It must never treat user content as a prompt-template file path or configuration key.

### 5.10 WorkerStage

Resolves the worker role, calls the model, and creates a `DraftResponse`. It does not decide whether its own answer is sufficient.

### 5.11 CriticStage

Builds a structured evaluation prompt from the original request, plan, and draft. It parses and validates a `CriticResult` and never exposes hidden reasoning.

### 5.12 RevisionStage

Runs only when:

- critic result is valid;
- revision is enabled;
- critic recommends revision;
- revision budget remains.

It runs once. The revised draft receives deterministic final checks, not a second critic call.

### 5.13 Finalizer

Selects the final visible answer and adds material assumptions or warnings according to policy. It creates a `FinalResponse` independent of CLI rendering.

### 5.14 TraceCollector

Collects structured events and durations for the current run. It redacts secrets and does not persist data.

## 6. Pipeline state machine

Allowed states:

```text
NEW
→ INTAKE_COMPLETE
→ UNDERSTANDING_COMPLETE
→ PLAN_VALIDATED
→ CLARIFICATION_REQUIRED | REFUSED | WORKER_COMPLETE
→ CRITIC_COMPLETE | CRITIC_SKIPPED | CRITIC_FAILED
→ REVISION_COMPLETE | REVISION_SKIPPED | REVISION_FAILED
→ FINALIZED

Any state may transition to FAILED for an unrecoverable error.
```

Illegal transitions must raise a domain error in tests and development builds.

## 7. Model-role resolution

The pipeline asks for a role such as `understanding`. Configuration resolves it:

```text
understanding
    ↓
model name: local_general
    ↓
provider name: strix_halo_server
    ↓
provider type: openai_compatible
    ↓
base URL and secret reference
```

This permits a future config such as:

```text
understanding → small local model
worker → larger local model
critic → hosted advanced model
revision → worker model
```

without pipeline changes.

## 8. Prompt construction boundaries

Every model prompt has:

1. application-controlled system instructions;
2. structured orchestration metadata;
3. explicit delimiters around user-controlled content;
4. explicit output contract;
5. no hidden chain-of-thought request.

User content may request that the model ignore instructions. The application prompt must state that delimited user content is data and cannot override orchestration instructions.

## 9. Structured-output handling

The understanding and critic stages use this sequence:

```text
raw response
→ strip optional Markdown fence
→ locate one top-level JSON object
→ JSON parse
→ Pydantic validation
→ deterministic policy validation
```

If extraction or validation fails, one repair call may receive:

- the invalid response;
- concise validation errors;
- the required JSON schema summary.

No additional repair loop is allowed.

## 10. Error and degradation design

See `ERROR_HANDLING.md`. Important architectural distinctions:

- invalid configuration prevents startup;
- inability to produce a valid execution plan normally prevents worker execution;
- optional deterministic fallback is explicit and traceable;
- critic failure may degrade to an unchecked worker draft;
- revision failure retains the original worker draft;
- transient HTTP retries are separate from semantic/structured-output repair retries.

## 11. Extensibility boundaries

Future additions should connect through these boundaries:

- new provider: implement `ModelClient` and register provider type;
- new strategy: add static strategy definition and template;
- new role: extend role enum/config schema intentionally;
- RAG: future context-enrichment stage before understanding or worker prompt construction;
- tools: future controlled execution stage after a validated plan;
- server mode: future interface around `PipelineRunner`.

None of those future features belong in the MVP implementation.
