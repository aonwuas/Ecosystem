# MVP: Prompt Orchestrator

## Product Goal

Create a prompt orchestration ecosystem that improves LLM performance across a variety of tasks by adding a structured control layer before and after generation.

The product is not a model. It is a runtime that decides how a model should be used for a specific prompt.

The MVP should prove this thesis:

> Better prompt intake, classification, strategy selection, prompt construction, and lightweight output review can improve model behavior even without RAG or tools.

## Target User

The initial user is a person interacting with an LLM through a CLI. The user provides a prompt and expects a useful answer.

The system should work across broad categories, not just software engineering.

Examples:

- “Help me write a professional email.”
- “Summarize this text.”
- “Compare these options.”
- “Explain this concept.”
- “Help me plan a project.”
- “Brainstorm names for this product.”
- “Make this paragraph friendlier.”
- “Should I make this financial decision?”

## Core MVP Capabilities

The MVP should:

1. Accept a prompt.
2. Normalize the prompt into a structured request.
3. Extract explicit constraints and requested output format.
4. Determine the user’s intent.
5. Determine the prompt/task type.
6. Determine task complexity.
7. Detect ambiguity and missing information.
8. Detect risk or sensitivity level.
9. Decide whether to ask a follow-up question, proceed with assumptions, refuse/redirect, or answer directly.
10. Select a response strategy.
11. Select a model role or prompt template.
12. Build an optimized internal prompt.
13. Generate a draft answer through a model client abstraction.
14. Run a lightweight quality check.
15. Return the final answer, including assumptions or limitations when useful.

## Non-Goals

The MVP must not include:

- RAG
- embeddings
- vector database
- retrieval over documents
- retrieval over code repositories
- external tools
- shell execution
- function calling / tool calling
- web browsing
- database persistence
- long-term memory
- multi-user support
- server deployment
- web UI
- user accounts
- authentication
- background jobs
- agent workspaces

## Product Boundary

The MVP is a single-user, local, CLI-first orchestration layer.

It should be possible to run and test the full pipeline without a real model endpoint by using a mock model client.

A real model client may be supported as a configuration option, but it is not required for tests.

## Prompt Categories

The MVP should recognize these broad task types:

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

The implementation may represent these as enums or string constants.

## Intent Categories

Intent describes what the user is trying to accomplish.

Useful intent values include:

- `get_answer`
- `understand_topic`
- `create_text`
- `improve_text`
- `condense_information`
- `convert_language`
- `generate_ideas`
- `make_plan`
- `evaluate_options`
- `make_decision`
- `analyze_content`
- `extract_information`
- `produce_structured_output`
- `solve_problem`
- `chat`
- `unknown`

## Complexity Levels

The MVP should estimate complexity as:

- `simple`
- `moderate`
- `complex`
- `multi_step`
- `high_stakes`

Guidance:

`simple`:
- direct Q&A
- small rewrite
- short explanation

`moderate`:
- comparison
- plan with a few steps
- moderate analysis

`complex`:
- multiple constraints
- broad planning
- several possible interpretations
- long-form output

`multi_step`:
- requires decomposition
- requires a staged answer
- combines several sub-tasks

`high_stakes`:
- legal, medical, financial, safety, privacy, or irreversible decisions

## Ambiguity Detection

The MVP should detect prompts that are missing required information.

Common ambiguity signals:

- “this” without provided content
- “it” without a clear referent
- “the above” without context
- “make it better” with no target text
- “write a reply” without the message to reply to
- requested format is unclear when format is critical
- audience or tone is missing for a high-context writing request

Ambiguity levels:

- `none`
- `low`
- `medium`
- `high`

The system should ask a follow-up only when needed. It should not over-ask.

## Risk and Sensitivity Detection

Risk/sensitivity categories:

- `none`
- `medical`
- `legal`
- `financial`
- `security`
- `privacy`
- `personal_crisis`
- `dangerous_instructions`
- `academic_integrity`
- `employment_sensitive`
- `reputation_sensitive`

High-stakes prompts should be answered cautiously and should not present the model as an authority.

Dangerous or disallowed prompts should be routed to a safety redirect strategy.

## Clarification Decisions

The clarification gate should return one of:

- `answer_now`
- `ask_followup`
- `proceed_with_assumptions`
- `refuse_or_redirect`

Ask a follow-up when the task cannot be completed usefully without missing information.

Proceed with assumptions when assumptions are safe and the answer can still be useful.

Refuse/redirect only for unsafe or disallowed requests.

## Response Strategies

The MVP should support at least these strategies:

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

Each response strategy should map to a prompt template.

## Model Roles

Even if the MVP uses one mock model, the architecture should include logical model roles:

- `generalist`
- `writer`
- `rewriter`
- `summarizer`
- `planner`
- `analyst`
- `critic`
- `safety`

For the MVP, these roles may all route to the same mock client. The purpose is to make the architecture expandable later.

## Internal Prompt Construction

The prompt builder should produce a structured internal prompt containing:

- original user prompt
- normalized task description
- intent
- task type
- complexity
- risk/sensitivity classification
- explicit constraints
- requested output format
- assumptions
- selected response strategy
- instructions specific to the strategy
- output requirements

The internal prompt should be testable as a string or structured object.

## Quality Check

The MVP should include a lightweight quality check that verifies:

- the answer addresses the user prompt
- the selected strategy was followed
- requested format was followed when explicit
- important constraints were respected
- high-stakes prompts include appropriate caution
- clarification was not required but ignored

The quality check should not loop indefinitely.

At most one revision pass is allowed in the MVP.

## CLI Commands

Expected final CLI commands:

```bash
prompt-orchestrator classify "..."
prompt-orchestrator plan "..."
prompt-orchestrator run "..."
prompt-orchestrator run --json "..."
```

Optional useful commands:

```bash
prompt-orchestrator templates
prompt-orchestrator examples
```

Do not add commands that require tools, files, RAG, or servers.

## Example Behavior

### Ambiguous writing request

Prompt:

```text
Make this better.
```

Expected behavior:

- task type: rewrite
- ambiguity: high
- clarification decision: ask_followup
- final response: asks user to provide the text to improve

### Planning request

Prompt:

```text
Help me plan a small local-first note taking app.
```

Expected behavior:

- task type: planning
- complexity: moderate
- strategy: plan_generation
- final response: structured plan

### Comparison request

Prompt:

```text
Compare SQLite and Postgres for a small internal tool.
```

Expected behavior:

- task type: comparison
- strategy: pros_cons_comparison
- final response: structured comparison with recommendation framing

### High-stakes financial request

Prompt:

```text
Should I invest all my savings in this company?
```

Expected behavior:

- risk: financial
- complexity: high_stakes
- strategy: decision_support
- final response: cautious, non-prescriptive guidance

## Definition of MVP Complete

The MVP is complete when:

- all checkpoint acceptance criteria pass
- CLI commands work
- the full pipeline works with mock model responses
- classifications are structured and serializable
- prompt templates render correctly
- quality check can pass/fail and request one revision
- README contains usage examples
- no out-of-scope features have been added
