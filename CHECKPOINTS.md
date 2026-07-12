# Checkpoints

Use these checkpoints to build the MVP incrementally with Codex.

General instruction for every checkpoint:

```text
Read AGENTS.md, MVP.md, ARCHITECTURE.md, and CHECKPOINTS.md.
Implement only the requested checkpoint.
Do not implement later checkpoints.
Do not add RAG, tools, web UI, database persistence, server mode, or external integrations.
Add or update tests.
Run tests.
Summarize files changed, tests run, and unresolved issues.
Stop.
```

## Checkpoint 1: Project Skeleton

### Goal

Create the initial Python project structure.

### Implement

- `pyproject.toml`
- `src/prompt_orchestrator/__init__.py`
- `src/prompt_orchestrator/cli.py`
- basic CLI entrypoint named `prompt-orchestrator`
- `tests/` directory
- basic pytest smoke tests
- optional `examples/` directory

### Do Not Implement

- classifier
- pipeline
- model client
- prompt templates
- RAG
- tools

### Acceptance Criteria

- Package imports successfully.
- CLI help command runs.
- `pytest` passes.
- README remains consistent with the project.

---

## Checkpoint 2: Core Data Models

### Goal

Define the structured objects that flow through the pipeline.

### Implement

Core models such as:

- `PromptRequest`
- `NormalizedPrompt`
- `PromptClassification`
- `ClarificationDecision`
- `ResponseStrategyDecision`
- `PromptPlan`
- `GenerationResult`
- `QualityCheckResult`
- `FinalResponse`

Use dataclasses or Pydantic. Prefer dataclasses unless validation complexity justifies Pydantic.

### Required Traits

- serializable to dict/JSON
- typed fields
- clear enum/string values
- sensible defaults where appropriate

### Acceptance Criteria

- Models can be instantiated in tests.
- Models serialize to dictionaries.
- Tests cover representative valid objects.
- Invalid or unknown enum-like values are handled clearly if validation is implemented.

---

## Checkpoint 3: Prompt Intake

### Goal

Normalize incoming prompts and extract simple surface-level constraints.

### Implement

- intake function/class
- whitespace normalization
- empty prompt handling
- requested output format detection
- simple explicit constraint extraction

Examples of constraints/output format:

- “be concise”
- “use bullets”
- “return JSON”
- “make it professional”
- “friendly tone”
- “step by step”

### Acceptance Criteria

- Empty prompt is detected.
- Whitespace is normalized without losing original prompt.
- Requested JSON/bullets/numbered list can be detected.
- Tone/length constraints can be detected for obvious cases.
- Tests pass.

---

## Checkpoint 4: Deterministic Classifier

### Goal

Classify prompts without calling an LLM.

### Implement

- intent classification
- task type classification
- complexity classification
- ambiguity detection
- missing information detection
- risk/sensitivity detection

Task types should include at least:

- `qa`
- `explanation`
- `writing`
- `rewrite`
- `summarization`
- `translation`
- `brainstorming`
- `planning`
- `analysis`
- `comparison`
- `decision_support`
- `classification`
- `extraction`
- `structured_output`
- `creative_generation`
- `technical_help`
- `debugging`
- `conversation`
- `unknown`

### Acceptance Criteria

Tests cover at least:

- direct Q&A
- explanation
- rewrite request with provided text
- rewrite request missing text
- summarization request
- planning request
- comparison request
- brainstorming request
- high-stakes financial/legal/medical prompt
- dangerous instruction prompt
- ambiguous “make this better” prompt

---

## Checkpoint 5: Clarification Gate

### Goal

Decide whether the system should answer now, ask a follow-up, proceed with assumptions, or refuse/redirect.

### Implement

Clarification actions:

- `answer_now`
- `ask_followup`
- `proceed_with_assumptions`
- `refuse_or_redirect`

The gate should consider:

- ambiguity level
- missing information
- task type
- risk/sensitivity
- whether assumptions would be safe

### Acceptance Criteria

- “Make this better” without target text asks for text.
- “Write a reply” without message asks for the message or context.
- A planning prompt with mild missing detail proceeds with assumptions.
- Dangerous instruction prompts refuse/redirect.
- High-stakes prompts proceed cautiously rather than asking unnecessary questions.
- Tests pass.

---

## Checkpoint 6: Response Strategy Selector

### Goal

Choose the response strategy and logical model role.

### Implement

Strategies:

- `direct_answer`
- `step_by_step_explanation`
- `structured_analysis`
- `pros_cons_comparison`
- `decision_support`
- `draft_generation`
- `rewrite_with_preserved_meaning`
- `summarization`
- `brainstorm_options`
- `plan_generation`
- `classification_response`
- `extraction_response`
- `structured_output_response`
- `clarify_first`
- `safety_redirect`

Model roles:

- `generalist`
- `writer`
- `rewriter`
- `summarizer`
- `planner`
- `analyst`
- `critic`
- `safety`

### Acceptance Criteria

- Each major task type maps to an expected strategy.
- Clarification decision `ask_followup` maps to `clarify_first`.
- Refuse/redirect maps to `safety_redirect`.
- High-stakes decision prompts map to `decision_support`.
- Tests cover every strategy.

---

## Checkpoint 7: Prompt Template System

### Goal

Build optimized internal prompts from selected strategies.

### Implement

- prompt template registry
- template rendering
- templates for all MVP strategies
- `PromptPlan` construction

Each rendered prompt should include:

- original prompt
- normalized prompt
- intent
- task type
- complexity
- risk/sensitivity
- explicit constraints
- requested output format
- assumptions
- strategy-specific instructions

### Acceptance Criteria

- Every strategy has a template.
- Missing template returns a clear error.
- Rendered prompts include required fields.
- Tests verify template rendering for several task types.
- No model calls are required.

---

## Checkpoint 8: Model Client Abstraction

### Goal

Allow generation without binding the runtime to a specific model provider.

### Implement

- `ModelClient` protocol/interface
- `MockModelClient`
- simple generation request/response objects if needed
- optional config object for future real providers

Do not require live model endpoints.

### Acceptance Criteria

- Tests use `MockModelClient`.
- Mock client can return deterministic responses.
- Mock client can simulate failure.
- Pipeline code can depend on the interface, not a concrete provider.
- Tests pass without network access.

---

## Checkpoint 9: Generation Pipeline

### Goal

Run the core path from prompt to generated draft.

### Implement

Pipeline stages:

1. intake
2. classification
3. clarification decision
4. strategy selection
5. prompt plan generation
6. draft generation through model client

The pipeline should stop early if clarification or refusal is required.

### Acceptance Criteria

- Normal prompts produce a `GenerationResult`.
- Ambiguous prompts return a clarification-style `FinalResponse` or equivalent early stop result.
- Dangerous prompts return a safety redirect result.
- Pipeline trace is available for debugging/tests.
- Tests cover normal, ambiguous, and safety cases.

---

## Checkpoint 10: Lightweight Quality Check

### Goal

Review generated draft before finalization.

### Implement

- quality check function/class
- deterministic checks for obvious issues
- optional one-pass revision with the mock model
- `QualityCheckResult`

Checks should include:

- empty response
- ignored requested output format where detectable
- high-stakes answer lacks caution
- clarification was required but ignored
- response does not address prompt in obvious cases if detectable

### Acceptance Criteria

- Passing response passes.
- Empty response fails.
- Missing requested JSON/bullets can fail when requested.
- High-stakes response without caution can fail.
- At most one revision pass is allowed.
- Tests pass.

---

## Checkpoint 11: Finalizer and Full Pipeline

### Goal

Return a complete final response object from the full pipeline.

### Implement

- finalization logic
- assumption/limitation handling
- final text selection
- quality check integration
- full pipeline runner

### Acceptance Criteria

- `run()` returns `FinalResponse`.
- Final response includes final text, strategy, assumptions, limitations, and quality result.
- Clarification outputs are formatted cleanly.
- Safety redirect outputs are formatted cleanly.
- Tests cover full end-to-end behavior with mock client.

---

## Checkpoint 12: CLI Commands

### Goal

Expose the MVP through a usable CLI.

### Implement

Commands:

- `prompt-orchestrator classify "..."`
- `prompt-orchestrator plan "..."`
- `prompt-orchestrator run "..."`
- `--json` option for structured output where appropriate

### Acceptance Criteria

- CLI commands work.
- CLI commands return nonzero exit code for invalid input where appropriate.
- `classify` prints classification.
- `plan` prints prompt plan.
- `run` prints final response.
- `--json` prints valid JSON.
- CLI tests pass.

---

## Checkpoint 13: Examples and README Polish

### Goal

Make the MVP understandable and demonstrable.

### Implement

- examples for different prompt types
- README usage section
- README architecture summary
- README non-goals reminder
- example CLI outputs if practical

Example categories:

- ambiguous rewrite
- planning
- comparison
- brainstorming
- high-stakes decision support
- summarization
- explanation

### Acceptance Criteria

- README explains what the MVP does.
- README explains what is intentionally not included.
- Examples can be run manually.
- Tests still pass.

---

## Checkpoint 14: Cleanup and Consistency Pass

### Goal

Clean up the MVP without adding scope.

### Implement

- remove dead code
- improve naming consistency
- ensure object serialization is consistent
- ensure docs match CLI behavior
- ensure tests are organized
- ensure no out-of-scope features were added

### Acceptance Criteria

- Full test suite passes.
- README, MVP, ARCHITECTURE, and CHECKPOINTS are consistent.
- No RAG/tools/server/database/web UI code exists.
- The CLI demonstrates the full MVP.
