# AGENTS.md

This file gives coding-agent instructions for building the Prompt Orchestrator MVP.

## Project Summary

This repository implements a minimum viable prompt orchestration runtime. The product improves LLM outputs by routing user prompts through a structured decision process before generation.

The runtime should classify the prompt, detect ambiguity/risk, choose a response strategy, build an optimized internal prompt, generate a response through a model client abstraction, optionally critique the draft, and return a final answer.

## Hard Scope Boundaries

Do **not** implement any of the following in the MVP:

- RAG
- vector search
- embeddings
- file/document search
- external tools
- shell execution by the runtime
- web browsing
- tool/function calling
- persistent memory
- database storage
- task queue
- server mode
- web UI
- authentication
- multi-user support
- coding-agent file editing

If a future checkpoint appears to require one of these, stop and report the conflict instead of implementing it.

## Implementation Rules

- Implement one checkpoint at a time.
- Do not skip ahead to future checkpoints.
- Do not combine multiple checkpoints unless explicitly instructed.
- Keep the project CLI-first.
- Use Python.
- Use a `src/` layout.
- Prefer standard library and lightweight dependencies.
- Use typed dataclasses or Pydantic models for internal objects.
- If adding a dependency, justify it and keep it minimal.
- Tests must not require a live model endpoint.
- Use a mock model client in tests.
- Keep model provider logic behind an interface.
- Keep the deterministic classifier separate from any future LLM-assisted classifier.
- Make output objects serializable to dictionaries/JSON.
- Keep the full pipeline traceable for debugging.

## Preferred Technology Choices

Unless otherwise instructed:

- Python 3.11+
- `pytest` for tests
- `typer` or `argparse` for CLI; prefer `argparse` if avoiding dependencies
- `dataclasses` or `pydantic`; prefer `dataclasses` for minimal dependencies unless validation complexity justifies Pydantic
- Plain Markdown prompt templates
- No database
- No web framework

## Code Style

- Keep modules small and focused.
- Prefer explicit names over clever abstractions.
- Use enums or string literal constants for controlled values.
- Validate unknown enum values at boundaries.
- Keep deterministic logic easy to test.
- Avoid hidden global state.
- Use dependency injection for model clients.
- Keep CLI rendering separate from pipeline logic.

## Testing Requirements

Each checkpoint should add or update tests.

Tests should cover:

- expected classification behavior
- ambiguity detection
- risk detection
- clarification decision behavior
- response strategy selection
- prompt template rendering
- mock generation behavior
- quality-check decisions
- pipeline end-to-end behavior with a mock model
- CLI smoke behavior

Tests must be runnable with:

```bash
pytest
```

If a different command is configured in `pyproject.toml`, document it in the README.

## CLI Behavior

The final MVP should expose:

```bash
prompt-orchestrator classify "..."
prompt-orchestrator plan "..."
prompt-orchestrator run "..."
```

`classify` should print classification data.

`plan` should print the classification, clarification decision, selected response strategy, and prompt plan.

`run` should execute the full pipeline and print the final response.

A `--json` option should output structured JSON where practical.

## Pipeline Design Rules

The core pipeline is:

```text
PromptRequest
  -> PromptIntake
  -> PromptClassification
  -> ClarificationDecision
  -> ResponseStrategy
  -> PromptPlan
  -> GenerationResult
  -> QualityCheckResult
  -> FinalResponse
```

The pipeline must be able to stop early when clarification is required.

The pipeline must not call a real model during unit tests.

## Classification Rules

Use deterministic rules first.

The classifier should identify at least:

- user intent
- task type
- complexity
- ambiguity level
- missing information
- risk/sensitivity level
- requested output format when explicit
- explicit constraints when obvious

Do not use an LLM for classification in the MVP unless a later checkpoint explicitly adds optional model-assisted classification.

## Clarification Rules

Ask a follow-up question only when:

- the task cannot be completed without missing information
- a wrong assumption would likely make the answer useless
- safety/risk depends on missing information
- the user clearly references absent content such as “this,” “it,” or “the above”

Otherwise, proceed with reasonable assumptions and expose important assumptions in the final answer when useful.

## Quality Check Rules

The quality check should be lightweight.

It should verify:

- the answer follows the selected strategy
- the answer addresses the user prompt
- requested format was followed when present
- constraints were not ignored
- clarification was not still required
- high-stakes prompts were handled cautiously

The MVP may use deterministic quality checks and/or a mock critic. It should not require a live model.

Do not create an infinite revise loop. At most one revision pass in the MVP.

## Safety and Refusal Behavior

The MVP should include basic risk/sensitivity detection, but it does not need a complex safety system.

For dangerous or disallowed requests, the pipeline should select a `safety_redirect` strategy and return a safe final response.

For high-stakes but allowed requests, the pipeline should provide cautious, non-authoritative guidance and state limitations.

## Milestone Discipline

When instructed to implement a checkpoint:

1. Read `AGENTS.md`, `MVP.md`, `ARCHITECTURE.md`, and `CHECKPOINTS.md`.
2. Implement only the requested checkpoint.
3. Do not implement later checkpoints.
4. Add or update tests.
5. Run tests.
6. Summarize files changed.
7. Summarize tests run.
8. List unresolved issues, if any.
9. Stop.

## Definition of Done for a Checkpoint

A checkpoint is done only when:

- its acceptance criteria are met
- tests pass or failures are clearly reported
- the implementation does not add out-of-scope features
- the code remains consistent with the architecture docs

## If Unsure

If a requirement is ambiguous, prefer the smallest implementation that satisfies the checkpoint.

Do not expand scope to “make it production-ready.” This repository is an MVP.
