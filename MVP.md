# Minimum Viable Product Specification

## 1. Product goal

Create a general-purpose orchestration runtime that improves LLM performance across writing, analysis, explanation, planning, comparison, summarization, transformation, technical assistance, creative work, and other text-based tasks.

The runtime improves performance by separating task understanding from task execution and by evaluating the generated draft against an explicit plan.

## 2. Core hypothesis

A worker model should receive a prompt that already identifies:

- the user's actual goal;
- the type and complexity of work;
- important constraints;
- missing information and assumptions;
- the best supported response strategy;
- the requested output contract;
- concrete quality criteria.

A separate critic pass should identify whether the draft followed that plan.

## 3. Primary users

### Local-model user

A user runs one or more local OpenAI-compatible model servers and maps model roles to those endpoints through YAML configuration.

### Hybrid local/API user

A future user may map some roles to local models and others to hosted providers. The MVP architecture must permit this without requiring pipeline changes, even though only generic OpenAI-compatible HTTP is implemented initially.

### Developer and evaluator

A developer uses mock or scripted model clients to test strategies, prompts, parsing, and pipeline behavior without a live model server.

## 4. Primary user experience

The user submits a prompt:

```bash
prompt-orchestrator run "Create a practical study plan for learning linear algebra"
```

The runtime:

1. normalizes the request;
2. calls the understanding role;
3. validates the returned execution plan;
4. returns a clarification question if required;
5. otherwise builds a worker prompt from a registered strategy;
6. calls the worker role;
7. calls the critic role;
8. optionally calls the revision role once;
9. prints the final answer.

The orchestration is hidden by default. The user can inspect it with `understand`, `plan`, `--trace`, or `--json`.

## 5. Functional requirements

### FR-1: Prompt intake

The system must accept:

- prompt text as a CLI argument;
- prompt text from standard input;
- optional conversation/context text supplied by the caller;
- optional explicit output-format override;
- optional configuration path.

It must reject an empty request with a clear message.

### FR-2: Model-driven understanding

The system must call the configured `understanding` role with a fixed prompt contract.

The understanding output must contain a structured `ExecutionPlan` describing:

- user goal;
- intent;
- task type;
- complexity;
- ambiguity;
- risk level and categories;
- missing information;
- assumptions;
- clarification decision;
- selected registered strategy;
- selected configured worker role;
- output contract;
- must-include and must-avoid constraints;
- quality criteria;
- uncertainties and concise rationale.

### FR-3: Deterministic validation and policy

The system must validate:

- JSON syntax and required fields;
- enum values;
- strategy registration;
- role registration;
- maximum lengths and list sizes;
- clarification consistency;
- output-format support;
- revision and retry limits;
- policy constraints for sensitive tasks.

The execution plan is not used until validation succeeds.

### FR-4: Clarification gate

The system must support these outcomes:

- `proceed`;
- `ask_clarification`;
- `refuse_or_redirect`.

When clarification is required, the CLI prints one focused question and stops. The MVP does not keep a persistent session.

### FR-5: Registered response strategies

The MVP must support at least:

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

The understanding model chooses only from this registry. Strategy metadata determines the worker prompt template and default output behavior.

### FR-6: Prompt construction

The worker prompt must include:

- a stable system instruction for the selected strategy;
- the original user request in explicit delimiters;
- supplied context in separate delimiters;
- execution-plan summary;
- assumptions;
- must-include constraints;
- must-avoid constraints;
- output contract;
- quality criteria.

It must not include hidden chain-of-thought requests.

### FR-7: Model provider configuration

The runtime must load YAML defining:

- providers;
- named models;
- role bindings;
- runtime limits;
- critic policy;
- trace policy.

Configuration must support local endpoints with no API key and API-key lookup through environment variables.

### FR-8: Worker generation

The system must call the configured worker role using the built prompt and return a draft result with request metadata and usage metadata when available.

### FR-9: Critic review

The critic must evaluate the draft against the plan and return structured findings:

- pass/fail;
- issue list;
- violated criteria;
- whether revision is recommended;
- concise revision instruction.

### FR-10: One-pass revision

When enabled and recommended:

- call the configured revision role once;
- provide the original request, validated plan, draft, and concise revision instruction;
- return the revised answer if successful;
- never enter a second critic/revision loop.

### FR-11: Final response

The final result must indicate:

- final answer text or clarification question;
- status;
- strategy used;
- roles/models selected;
- assumptions disclosed to the user when material;
- critic status;
- whether revision occurred;
- warnings and degraded-mode notices.

Default CLI display prints a clean user-facing answer. JSON mode exposes the structured result.

### FR-12: Traceability

Trace mode must capture sanitized summaries for:

- intake;
- understanding request and response status;
- parsed execution plan;
- policy changes or fallback behavior;
- worker role and strategy;
- critic result;
- revision result;
- timing and retry counts.

No trace persistence is required.

### FR-13: Testability

The complete pipeline must run with scripted model responses and no network access.

## 6. Non-functional requirements

- Predictable: all loops and retries are bounded.
- Configurable: no provider URL or model name is hardcoded.
- Inspectable: users can view plans and traces.
- Testable: default tests need no live server.
- Extensible: new providers, strategies, and model roles can be added behind registries/interfaces.
- Safe by construction: user prompts are delimited data, secrets are not logged, and model outputs are validated.
- Portable: supported on Windows and Linux with repository-controlled LF line endings.

## 7. Non-goals

The MVP does not implement:

- RAG;
- tools or function calling;
- file access by the runtime;
- code execution;
- browsing;
- persistent chat sessions;
- persistent traces;
- database storage;
- automatic provider/model benchmarking;
- automatic cost-based escalation;
- streaming output;
- parallel model calls;
- multi-user service mode;
- GUI or web UI.

## 8. MVP completion criteria

The MVP is complete when:

1. configuration validation works for mock and OpenAI-compatible providers;
2. all documented CLI commands work;
3. the full pipeline works with scripted models;
4. a live OpenAI-compatible endpoint can be used through configuration;
5. understanding and critic structured outputs are robustly parsed and validated;
6. clarification stops execution correctly;
7. at most one revision can occur;
8. all retries are bounded;
9. traces are sanitized;
10. README examples match implemented behavior;
11. linting, formatting checks, type checking, and tests pass;
12. prohibited MVP scope has not been added.
