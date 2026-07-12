# Architecture

## Overview

Prompt Orchestrator is a CLI-first orchestration runtime that improves LLM interactions by converting a raw user prompt into a structured response process.

The MVP does not use RAG or tools. It relies on prompt intake, deterministic classification, strategy selection, internal prompt construction, model abstraction, and lightweight quality checking.

```text
User Prompt
  -> Prompt Intake
  -> Deterministic Classifier
  -> Clarification Gate
  -> Strategy Selector
  -> Prompt Builder
  -> Model Client
  -> Quality Checker
  -> Finalizer
  -> Final Response
```

## Design Principles

- Keep the MVP small and testable.
- Use deterministic rules before model-based routing.
- Keep model calls behind an interface.
- Keep internal state serializable.
- Make each pipeline phase independently testable.
- Allow future expansion without implementing future features now.
- Do not add RAG, tools, web UI, database, or server mode.

## Core Modules

Target module structure:

```text
src/prompt_orchestrator/
  __init__.py
  cli.py
  models.py
  intake.py
  classifier.py
  clarification.py
  strategies.py
  prompt_templates.py
  model_client.py
  pipeline.py
  quality.py
  finalizer.py
```

Additional helper modules may be added if they simplify the implementation, but avoid unnecessary abstractions.

## Core Data Flow

### 1. PromptRequest

Created from user input.

Expected fields:

- raw prompt
- optional conversation context
- optional user constraints
- optional requested format
- optional metadata

The MVP may only support raw prompt from the CLI, but the object should allow future expansion.

### 2. PromptIntake

Normalizes the prompt and extracts simple surface-level facts.

Responsibilities:

- trim and normalize whitespace
- detect empty prompts
- detect explicit output format requests
- extract obvious constraints such as “be concise,” “use bullets,” “make it professional,” “return JSON”
- preserve the original prompt exactly

Output should update or create a normalized request object.

### 3. PromptClassification

Classifies the normalized request.

Responsibilities:

- intent classification
- task type classification
- complexity estimation
- ambiguity detection
- missing information detection
- risk/sensitivity detection
- output format detection if not already found during intake

Classification should be deterministic in the MVP.

### 4. ClarificationDecision

Decides whether the system should continue or stop to ask a question.

Possible actions:

- `answer_now`
- `ask_followup`
- `proceed_with_assumptions`
- `refuse_or_redirect`

Responsibilities:

- ask a follow-up only when the task cannot be completed usefully
- proceed with assumptions when safe
- route unsafe prompts to safety redirect
- create a concise follow-up question when needed
- create assumptions when proceeding despite missing details

### 5. ResponseStrategy

Selects how the answer should be generated.

Examples:

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

The strategy should determine:

- prompt template
- model role
- whether quality check is required
- whether a cautious tone is required
- whether assumptions should be shown

### 6. PromptPlan

The PromptPlan is the structured plan for model generation.

Expected fields:

- original prompt
- normalized prompt
- selected strategy
- model role
- prompt template name
- assumptions
- constraints
- requested output format
- internal prompt text
- quality check required flag

The plan is what the `plan` CLI command should display.

### 7. ModelClient

The model client abstracts generation.

MVP requirements:

- define a protocol/interface
- implement MockModelClient
- optionally implement a simple OpenAI-compatible client only if it does not complicate tests
- tests must use the mock client

The rest of the pipeline should not know whether the client is mock or real.

### 8. GenerationResult

Captures the model output.

Expected fields:

- text
- model role
- prompt template name
- raw model metadata if available
- whether generation succeeded
- error message if generation failed

### 9. QualityCheckResult

Evaluates the generated draft.

Expected fields:

- passed
- issues
- revision_needed
- revised_prompt, optional
- reason

The MVP may implement deterministic quality checks and/or use the mock model to simulate a critic.

At most one revision pass is allowed.

### 10. FinalResponse

The final object returned by the pipeline.

Expected fields:

- final text
- action taken
- classification summary
- strategy
- assumptions
- limitations
- quality check result
- pipeline trace, optional

## CLI Architecture

The CLI should be a thin layer over pipeline functions.

Commands:

### classify

Input:

```bash
prompt-orchestrator classify "..."
```

Output:

- structured classification
- JSON option if implemented

### plan

Input:

```bash
prompt-orchestrator plan "..."
```

Output:

- classification
- clarification decision
- selected strategy
- model role
- template name
- assumptions
- internal prompt preview

### run

Input:

```bash
prompt-orchestrator run "..."
```

Output:

- final answer or clarification question

With `--json`, output structured response.

## Template Architecture

Prompt templates should be plain text files or Python string constants.

A simple implementation may use Python dictionaries first. If template files are used, place them under:

```text
src/prompt_orchestrator/templates/
```

Each strategy should have a template.

Templates should receive:

- original prompt
- task type
- intent
- complexity
- risk
- constraints
- requested output format
- assumptions
- strategy-specific instructions

## Deterministic Classifier Architecture

The classifier should use explicit rules.

Suggested approach:

1. Lowercase prompt for rule matching.
2. Detect high-stakes/risk keywords.
3. Detect missing-content ambiguity patterns.
4. Detect task type by keyword and structure.
5. Detect intent from task type.
6. Estimate complexity from risk/task/wording.
7. Extract explicit constraints.
8. Return a structured classification object.

The classifier does not need to be perfect. It needs to be predictable and testable.

## Strategy Selector Architecture

The strategy selector maps classification + clarification decision to response strategy.

Example mappings:

```text
ask_followup -> clarify_first
risk dangerous_instructions -> safety_redirect
rewrite -> rewrite_with_preserved_meaning
summarization -> summarization
planning -> plan_generation
comparison -> pros_cons_comparison
financial/legal/medical high-stakes -> decision_support
explanation -> step_by_step_explanation
analysis -> structured_analysis
brainstorming -> brainstorm_options
qa -> direct_answer
```

## Quality Checker Architecture

Quality check should be deliberately lightweight.

The MVP should check:

- empty response
- generated response when clarification was required
- missing requested JSON/bullets/numbered list format if requested
- high-stakes answer lacks caution language
- response ignores explicit brevity/professional tone constraints where detectable

The quality checker may return pass/fail with issues.

If revision is enabled, allow only one revision.

## Error Handling

The system should handle:

- empty prompt
- unsupported command
- template missing
- model client failure
- quality check failure

Errors should be user-readable and testable.

## Serialization

Core objects should be serializable to dictionaries/JSON.

This supports:

- CLI `--json`
- tests
- future logging
- future UI/server mode

Do not add persistence in the MVP.

## Future Extension Points

Future features may include:

- RAG
- tool use
- model routing across multiple endpoints
- memory
- server mode
- web UI
- user profiles
- multi-pass planner/critic loops

The MVP should leave clean interfaces for these but must not implement them.
