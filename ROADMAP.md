# Prompt Orchestrator Feature Roadmap

## 1. Purpose

Prompt Orchestrator is a model-agnostic runtime intended to improve LLM performance through orchestration rather than relying on a single model call.

The long-term system should be able to:

* understand the user’s actual goal
* choose an appropriate reasoning and response process
* route work to suitable models
* break complex work into steps
* acquire relevant context when required
* invoke controlled external capabilities
* evaluate intermediate and final outputs
* recover from failures
* maintain task state
* integrate with coding harnesses and other AI clients
* support multiple users and shared infrastructure

The project is not limited to programming. It should support writing, analysis, planning, research, decision support, technical problem-solving, creative work, software engineering, and future task categories.

---

## 2. Planning documents

The project uses two complementary planning documents:

### `ROADMAP.md`

Describes:

* the intended product
* future phases
* dependencies between phases
* expected capabilities
* acceptance criteria
* features intentionally deferred

It should change when the product direction or phase definitions change.

### `PROJECT_STATE.md`

Describes:

* what the repository currently implements
* current architecture and module layout
* public interfaces and commands
* configuration structure
* prompt and schema contracts
* tests and known limitations
* completed and partially completed roadmap work
* extension points relevant to the next phase

It must be updated whenever implementation changes make any existing section inaccurate.

A planner should be able to read `ROADMAP.md` and `PROJECT_STATE.md` without prior conversation context and produce a detailed implementation plan for any unfinished phase.

---

## 3. Current baseline: Phase 0

The current MVP is assumed to provide a working single-model orchestration pipeline with logical roles such as:

* understanding
* worker
* critic
* revision

These roles may currently resolve to the same configured LLM.

The baseline pipeline is:

```text
User request
    ↓
Prompt intake
    ↓
Model-driven task understanding
    ↓
Validated execution plan
    ↓
Worker prompt construction
    ↓
Worker generation
    ↓
Critic evaluation
    ↓
Optional single revision
    ↓
Final response
```

The MVP should already include or approximate:

* provider and model configuration
* role-to-model resolution
* structured execution-plan output
* deterministic schema validation
* clarification decisions
* response strategy selection
* worker prompt generation
* critic evaluation
* a maximum of one revision pass
* CLI access
* mock or scripted model clients for testing
* basic trace output
* no RAG
* no external tools
* no persistent memory
* no multi-user service

Before beginning later phases, `PROJECT_STATE.md` must confirm which baseline capabilities actually exist.

---

# Phase 1 — Multi-model orchestration

## Goal

Allow logical roles to resolve to different models, providers, endpoints, and operating profiles.

The runtime should no longer assume that one model performs every stage.

## Capabilities

Add configurable model assignments for roles such as:

* understanding
* planner
* worker
* critic
* revision
* summarizer
* fallback

Support:

* several local `llama-server` endpoints
* multiple models hosted on the same endpoint
* OpenAI-compatible hosted APIs
* future provider adapters
* per-role generation parameters
* role-specific timeout and retry policies
* model availability checks
* explicit fallback chains

Example:

```yaml
roles:
  understanding:
    primary: local_fast
    fallbacks:
      - local_general

  planner:
    primary: local_reasoner

  worker:
    primary: local_general

  critic:
    primary: local_reviewer
    fallbacks:
      - hosted_reasoner
```

## Required architectural changes

* Separate logical roles from concrete model definitions.
* Introduce a model registry.
* Introduce provider capabilities and model metadata.
* Allow one model to serve several roles.
* Prevent prompts from directly selecting arbitrary untrusted endpoints.
* Record selected provider, model, and role in traces.
* Define controlled behavior when a model is unavailable.

## Model metadata

Model definitions should eventually support:

* provider
* endpoint
* provider model name
* context limit
* output-token limit
* supported structured-output mode
* supported tool protocol
* latency tier
* quality tier
* cost tier
* local or remote designation
* enabled status
* concurrency limit
* task strengths
* task weaknesses

## Acceptance criteria

* At least three logical roles can resolve to different configured models.
* All roles may still resolve to one model for simple deployments.
* The selected model is visible in trace output.
* Missing models produce controlled errors or configured fallback behavior.
* Unit tests require no live endpoints.
* Optional integration tests can exercise two or more live model endpoints.
* No task-specific strategy contains hardcoded endpoint information.

## Deferred

* automatic cost-based API escalation
* automatic benchmark-based model selection
* load balancing across replicas
* multi-user scheduling

---

# Phase 2 — Strategy-specific execution

## Goal

Replace the generic worker path with an extensible registry of task strategies.

A strategy describes how a particular kind of task should be prepared, executed, evaluated, and formatted.

## Initial strategy families

The system should support bounded strategies for:

* direct answer
* structured explanation
* technical explanation
* structured analysis
* comparison
* decision support
* planning
* brainstorming
* summarization
* rewriting
* long-form writing
* creative generation
* troubleshooting
* software planning
* coding-task preparation
* safety-conscious response
* clarification-first response

## Strategy definition

Each strategy should be able to define:

* strategy identifier
* intended task types
* worker role
* optional planner role
* critic role
* prompt template
* critic rubric
* output contract
* default assumptions policy
* clarification policy
* whether decomposition is allowed
* whether multi-step execution is required
* whether critic review is required
* maximum revision count
* permitted future context sources
* permitted future tool classes

## Required architectural changes

* Create a strategy registry.
* Move strategy behavior out of large conditionals.
* Version strategy prompt templates.
* Validate model-requested strategies against the trusted registry.
* Provide a generic fallback strategy.
* Add strategy-specific critic criteria.
* Add tests for strategy selection and rendering.

## Acceptance criteria

* The understanding stage chooses only registered strategies.
* Unknown strategies are rejected or replaced with the configured fallback.
* At least eight substantially different strategy paths are implemented.
* Each strategy has tests for prompt construction and output expectations.
* Strategy selection and final selected strategy appear in traces.
* Adding a strategy does not require modifying the core pipeline runner.

---

# Phase 3 — Multi-step planning and execution

## Goal

Allow complex tasks to be decomposed into bounded steps that can be executed, reviewed, and revised independently.

## Core flow

```text
User request
    ↓
Task understanding
    ↓
Task-level plan
    ↓
Step selection
    ↓
Step execution
    ↓
Step verification or critique
    ↓
Update task state
    ↓
Next step or replan
    ↓
Final synthesis
```

## Plan schema

A task plan should contain:

* task goal
* success criteria
* assumptions
* known constraints
* unresolved questions
* ordered steps
* dependencies between steps
* expected output of each step
* role assigned to each step
* strategy assigned to each step
* critic requirements
* replan conditions
* final synthesis requirements

Each step should contain:

* stable step identifier
* objective
* instructions
* required context
* expected result
* completion criteria
* dependencies
* status
* attempt count
* review status
* output reference

## Execution behavior

The system should support:

* executing one step at a time
* pausing after a step
* continuing automatically when allowed
* requesting clarification before a blocked step
* revising one failed step
* replanning remaining steps
* preserving completed work during replanning
* final synthesis from completed step outputs

## Guardrails

* Set maximum plan length.
* Set maximum step attempts.
* Set maximum total model calls.
* Prevent endless planner/critic loops.
* Prevent modification of completed steps without an explicit replan.
* Require stable identifiers for steps.
* Record why a replan occurred.
* Distinguish step failure from whole-task failure.

## Acceptance criteria

* A task can produce a validated multi-step plan.
* Steps execute in dependency order.
* Step results are retained for later synthesis.
* A failed step can be revised or trigger one bounded replan.
* Execution budgets are enforced.
* The task can pause and resume from serialized state.
* A final response can be generated from completed step outputs.
* Tests cover success, clarification, step failure, replan, and budget exhaustion.

---

# Phase 4 — Persistent task state and observability

## Goal

Make orchestration inspectable, resumable, and reproducible.

## Persistent task state

Store:

* task identifier
* original request
* caller context
* configuration snapshot
* execution plan
* current phase
* current step
* completed steps
* model calls
* selected roles and models
* prompt-template versions
* critic findings
* revisions
* failures
* assumptions
* final result
* timestamps

A simple local implementation may use JSON and JSONL files. A later service implementation may use a database.

## Suggested local layout

```text
.orchestrator/
  tasks/
    <task-id>/
      request.json
      config_snapshot.json
      execution_plan.json
      state.json
      events.jsonl
      outputs/
      final_response.json
```

## Observability

Add:

* structured event log
* trace levels
* duration per stage
* model-call counts
* token usage when supplied by the provider
* retry counts
* fallback usage
* redaction of secrets and sensitive headers
* inspect command
* resume command

## CLI examples

```bash
prompt-orchestrator inspect <task-id>
prompt-orchestrator resume <task-id>
prompt-orchestrator events <task-id>
```

## Acceptance criteria

* A multi-step task can be stopped and resumed.
* State remains valid after process restart.
* Trace events use stable schemas.
* Secrets are not stored.
* Configuration snapshots omit credentials.
* Failed tasks remain inspectable.
* Persisted state has schema-version migration support or a documented versioning policy.

---

# Phase 5 — Evaluation and regression framework

## Goal

Measure whether orchestration improves outputs and prevent regressions as models, prompts, and strategies change.

## Evaluation corpus

Create task suites covering:

* straightforward factual responses
* ambiguous requests
* clarification decisions
* planning
* technical explanations
* comparisons
* decision support
* writing
* rewriting
* summarization
* troubleshooting
* software planning
* adversarial formatting
* malformed structured output
* safety-sensitive categories
* multi-step execution

Each case may define:

* input prompt
* caller context
* expected strategy
* expected clarification behavior
* expected roles
* required answer properties
* prohibited answer properties
* expected number of steps
* expected critic requirement
* expected fallback behavior
* scoring rubric

## Evaluation types

Support:

* deterministic schema checks
* exact policy checks
* rubric-based model judging
* pairwise output comparison
* baseline versus orchestrated comparison
* strategy-selection accuracy
* malformed-output recovery
* latency and call-count measurement
* local versus hosted model comparison

## Version tracking

Evaluation reports should identify:

* application version or commit
* configuration profile
* model names
* model revisions where known
* prompt-template versions
* strategy versions
* evaluation-set version

## Acceptance criteria

* A repeatable CLI command runs the evaluation suite.
* Deterministic tests run without live models.
* Optional live evaluations can compare several configurations.
* Reports can compare direct-model output against orchestrated output.
* Regressions are visible by strategy and task category.
* Prompt-template changes can be evaluated before adoption.

---

# Phase 6 — Coding-harness planning and review mode

## Goal

Make Prompt Orchestrator useful alongside coding harnesses before placing it directly in their model/tool loop.

## Initial integration mode

The orchestrator should generate detailed artifacts for a coding harness:

* implementation plan
* repository-context request
* milestone breakdown
* checkpoint instructions
* acceptance criteria
* test requirements
* risk analysis
* review rubric
* follow-up repair prompt

## Coding-plan schema

A coding plan should include:

* requested feature or fix
* inferred project impact
* assumptions
* files or symbols likely needed
* context still required
* architectural risks
* implementation milestones
* exact next milestone
* scope exclusions
* test plan
* completion criteria
* rollback considerations
* reviewer checklist

## Outputs

Support:

```bash
prompt-orchestrator coding-plan "Implement feature XYZ"
prompt-orchestrator coding-review --input review-packet.json
prompt-orchestrator coding-repair --input review-result.json
```

## Harness handoff

Produce:

* human-readable Markdown
* structured JSON
* a copy-ready prompt for Codex or another coding harness

## Acceptance criteria

* A vague software request can become a bounded coding plan.
* The generated plan explicitly identifies missing repository context.
* The plan can be executed milestone by milestone.
* A diff and test report can be evaluated by the critic path.
* A failed review produces a bounded repair prompt.
* No direct code editing or shell execution is required in this phase.

---

# Phase 7 — API and service mode

## Goal

Expose orchestration as a reusable network service for clients, applications, and future team use.

## Initial API surface

Suggested endpoints:

```text
POST /v1/tasks/understand
POST /v1/tasks/plan
POST /v1/tasks/run
POST /v1/tasks/{task_id}/continue
POST /v1/tasks/{task_id}/cancel
GET  /v1/tasks/{task_id}
GET  /v1/tasks/{task_id}/events
GET  /v1/tasks/{task_id}/result
GET  /health
GET  /ready
```

## Service requirements

* request validation
* task identifiers
* asynchronous task execution
* bounded worker queue
* cancellation
* task status
* persistent state integration
* structured errors
* health and readiness checks
* configuration validation at startup
* provider availability checks
* API versioning

## Acceptance criteria

* CLI and API use the same library-level pipeline.
* A submitted task can be inspected while running.
* The service survives client disconnects.
* Concurrency limits are enforced.
* Invalid requests do not enter the worker queue.
* API schemas are documented.
* Service mode introduces no dependency from the core runtime onto a web framework.

---

# Phase 8 — Coding-harness compatibility and OpenAI-compatible facade

## Goal

Allow compatible clients and coding harnesses to use Prompt Orchestrator as though it were a model endpoint without breaking their message or tool protocols.

## Compatibility modes

Separate:

### Normal orchestration mode

Returns a polished final answer.

### Harness-native mode

Returns exactly the next assistant message expected by the harness.

Harness-native mode must preserve:

* system and developer instruction hierarchy
* complete message history
* structured tool definitions
* assistant tool-call syntax
* tool-call identifiers
* tool-result messages
* stop reasons where supported
* streaming event semantics
* response metadata required by the client

## OpenAI-compatible surface

Potential endpoints:

```text
POST /v1/chat/completions
POST /v1/responses
GET  /v1/models
```

Implementation should begin with one explicitly supported protocol rather than claiming broad compatibility.

## Risks

The proxy must not:

* wrap tool calls in prose
* rewrite valid structured output into normal text
* ask unnecessary follow-up questions
* hide messages required by the harness
* lose tool-call identifiers
* run the normal critic path in a way that corrupts protocol output
* alter the client’s system instructions
* silently drop unsupported fields

## Acceptance criteria

* At least one selected harness can complete a non-tool conversation through the facade.
* That harness can complete a simple tool-call loop without protocol corruption.
* Harness-native mode is isolated from normal response finalization.
* Unsupported fields and protocols fail explicitly.
* Compatibility is covered by recorded protocol fixtures.
* Direct-model fallback is available when orchestration is inappropriate.

---

# Phase 9 — RAG and context acquisition

## Goal

Give planners and workers access to relevant external or project-specific context without overloading model context windows.

## Retrieval flow

```text
Execution plan determines context need
    ↓
Context request is created
    ↓
Retrieval subsystem searches approved sources
    ↓
Results are filtered and ranked
    ↓
Structured context packet is created
    ↓
Planner or worker consumes exact context
    ↓
Critic evaluates context use
```

## Initial sources

Possible sources include:

* project documentation
* source code
* test code
* task history
* user-provided files
* organizational documentation

## Requirements

* source registry
* access controls
* source-specific metadata
* hybrid lexical and semantic search
* bounded result sets
* source citations or identifiers
* freshness metadata
* context-packet schema
* retrieval tracing
* exact-source reads before modifying code
* protection against cross-project retrieval

## Acceptance criteria

* The execution plan can request context without performing retrieval itself.
* Retrieval can be limited by source, project, branch, path, or document type.
* Context packets identify provenance.
* Retrieval failures degrade cleanly.
* The critic can detect unsupported claims or ignored context.
* RAG can be disabled without changing core orchestration.

---

# Phase 10 — Controlled tool execution

## Goal

Allow models to request actions through a policy-controlled capability system.

## Tool categories

Future tools may include:

* calculator
* structured data transformation
* web search
* file search
* filesystem read
* code execution
* shell execution
* email
* calendar
* database queries
* image analysis
* coding-harness actions

## Tool architecture

Add:

* tool registry
* JSON schemas
* role permissions
* strategy permissions
* project permissions
* user approval requirements
* execution budgets
* timeouts
* output-size limits
* result sanitization
* audit events
* cancellation
* idempotency where practical

## Core rule

```text
The model requests.
The runtime validates.
The policy authorizes.
The tool adapter executes.
The verifier evaluates.
```

## Acceptance criteria

* Tool requests are schema validated.
* Unknown tools are rejected.
* Role and strategy restrictions are enforced.
* Dangerous actions require explicit approval.
* Tool loops have hard budgets.
* Tool results are retained in task state.
* Failed tools produce structured results.
* A tool cannot access resources outside its granted scope.

---

# Phase 11 — Automatic model selection and escalation

## Goal

Choose among local and hosted models based on task requirements, availability, cost, latency, and measured quality.

## Selection inputs

* logical role
* strategy
* task complexity
* risk
* required context length
* required structured-output support
* required tool protocol
* model availability
* queue depth
* latency target
* cost policy
* evaluation results
* user or project preferences

## Escalation behavior

Examples:

* small local model for understanding
* stronger local planner for complex work
* specialized local coding model for coding plans
* hosted model only when explicitly permitted
* hosted escalation after bounded local failure
* local-only mode for private projects

## Guardrails

* API use must be configurable and auditable.
* Local-to-hosted escalation must not be silent.
* Sensitive context must not be sent to unapproved providers.
* Cost budgets must be enforced.
* Automatic routing must remain explainable through traces.

## Acceptance criteria

* Selection policy can be run in dry-run mode.
* Users can force local-only or named-model operation.
* Hosted escalation can require approval.
* The chosen model and reason are recorded.
* Evaluation results can inform but do not directly bypass policy.
* Provider outages trigger controlled fallback behavior.

---

# Phase 12 — Multi-user and shared deployment

## Goal

Support several users, projects, and concurrent tasks safely.

## Required capabilities

* authentication
* user and project identities
* per-project configuration
* role-based authorization
* isolated task state
* isolated context indexes
* queue scheduling
* per-model concurrency limits
* quotas
* API cost budgets
* audit logs
* task ownership
* cancellation permissions
* shared model pools
* replica awareness

## Scheduling

The scheduler should account for:

* task priority
* role requirements
* model availability
* GPU allocation
* per-user fairness
* maximum wait time
* API cost constraints
* local-versus-hosted policy

## Acceptance criteria

* Users cannot read one another’s private task state.
* Project configurations are isolated.
* Model concurrency limits are enforced.
* Queue starvation is prevented or measured.
* Tasks remain attributable to a user and project.
* Audit records cover model selection, approvals, tools, and hosted escalation.
* The service supports deployment with several model servers.

---

# Phase 13 — Production hardening

## Goal

Prepare the runtime for sustained use.

## Work areas

* configuration migration
* task-state migration
* provider resilience
* retry policy review
* circuit breakers
* structured logging
* metrics
* tracing
* health monitoring
* backup and recovery
* secret management
* rate limiting
* graceful shutdown
* deployment documentation
* security review
* load testing
* compatibility testing
* prompt-version management
* disaster recovery

## Acceptance criteria

* Configuration and persisted-state versions are explicit.
* Provider failures do not crash unrelated tasks.
* Service shutdown preserves resumable state.
* Logs and traces redact credentials.
* Metrics expose queue depth, latency, failures, and model usage.
* Load tests cover expected concurrency.
* Recovery procedures are documented and tested.

---

# Cross-cutting requirements

These apply to every phase.

## Model independence

Core orchestration must not depend on a specific model family.

## Provider independence

Provider behavior must remain behind adapter interfaces.

## Deterministic governance

Models may propose:

* roles
* strategies
* plans
* tools
* context needs
* escalation

Trusted application policy must validate and authorize them.

## Bounded loops

Every retry, revision, replan, critic, retrieval, and tool loop must have a hard limit.

## Structured state

Important orchestration decisions should use validated schemas rather than unstructured prose.

## Traceability

The runtime should record enough information to explain:

* what decision was made
* which role and model were selected
* which prompt-template version was used
* what failed
* why fallback or escalation occurred

## Security

User content must not be allowed to override trusted application instructions or configuration.

## Testability

Core behavior must be testable with mock and scripted clients.

## Replaceability

Prompts, strategies, provider adapters, storage, and evaluation components should be replaceable without rewriting the whole runtime.

---

# Recommended implementation order

The phases should generally be implemented in this order:

```text
Phase 1  Multi-model orchestration
Phase 2  Strategy-specific execution
Phase 3  Multi-step planning
Phase 4  Persistent task state and observability
Phase 5  Evaluation framework
Phase 6  Coding-harness planning and review
Phase 7  API and service mode
Phase 8  Harness compatibility and compatible facade
Phase 9  RAG
Phase 10 Controlled tools
Phase 11 Automatic model selection and escalation
Phase 12 Multi-user deployment
Phase 13 Production hardening
```

Some work may overlap, but later phases should not bypass the contracts established by earlier phases.

---

# Planner input contract

When requesting an implementation plan for a phase, provide the planner with:

1. `ROADMAP.md`
2. the current `PROJECT_STATE.md`
3. the target phase
4. any additional constraints for that implementation

Example request:

```text
Using ROADMAP.md and PROJECT_STATE.md, provide a detailed implementation plan for Phase 3 — Multi-step planning and execution.

The plan must:
- describe the current implementation relevant to this phase
- identify reusable components
- identify architectural gaps
- list files and modules likely to change
- define new schemas and interfaces
- divide implementation into bounded milestones
- include tests and acceptance criteria
- identify migration or compatibility concerns
- explicitly state what remains out of scope
```

The planner should treat `PROJECT_STATE.md` as a summary, not as a substitute for inspecting the repository during implementation.
