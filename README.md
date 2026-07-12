# Prompt Orchestrator MVP

Prompt Orchestrator is a CLI-first prompt orchestration runtime. Its goal is to improve LLM output quality across many task categories by adding a lightweight decision layer before generation.

The MVP intentionally does **not** include RAG, external tools, shell execution, web browsing, persistent memory, a database, a web UI, or a multi-user server. It focuses only on the core orchestration loop:

```text
prompt intake
  -> classification
  -> clarification decision
  -> response strategy selection
  -> internal prompt construction
  -> generation through a model client abstraction
  -> lightweight quality check
  -> final response
```

The first implementation should work entirely with mocked model calls so the project can be tested without a live LLM endpoint.

## Product Goal

Create an ecosystem layer that improves LLM performance across a variety of tasks by determining what kind of user request was made and shaping the model interaction accordingly.

The system should be useful for tasks such as:

- answering questions
- explaining concepts
- drafting writing
- rewriting text
- summarizing text
- brainstorming
- planning
- comparing options
- decision support
- technical help
- structured analysis
- classification/extraction-style tasks

## MVP Scope

The MVP should:

1. Accept a user prompt.
2. Normalize the prompt into a structured request.
3. Extract explicit constraints and requested output format.
4. Determine the user intent.
5. Determine the task or prompt type.
6. Determine task complexity.
7. Detect ambiguity and missing information.
8. Detect risk or sensitivity level.
9. Decide whether to ask a follow-up question, proceed with assumptions, refuse/redirect, or answer directly.
10. Select a response strategy.
11. Select a model role and prompt template.
12. Build an optimized internal prompt.
13. Generate a draft response through a model client abstraction.
14. Run a lightweight quality check.
15. Return the final response with assumptions or limitations when useful.

## Non-Goals

The MVP must not implement:

- RAG
- vector databases
- file search over user documents
- code search over repositories
- external tools
- shell execution by the runtime
- browser/web search
- long-term memory
- user accounts
- multi-user server mode
- web UI
- database persistence
- task queues
- coding-agent file editing
- function/tool calling

These may be future additions, but they are outside this MVP.

## CLI-first Interface

The initial product should expose a command named:

```bash
prompt-orchestrator
```

Expected commands by the end of the MVP:

```bash
prompt-orchestrator classify "Help me plan a small web app"
prompt-orchestrator plan "Help me plan a small web app"
prompt-orchestrator run "Help me plan a small web app"
prompt-orchestrator run --json "Help me plan a small web app"
```

The exact implementation can change slightly if needed, but the CLI must remain simple and testable.

## Expected User Experience

For a normal prompt, the system should produce an answer.

Example:

```bash
prompt-orchestrator run "Help me compare SQLite and Postgres for a small local app"
```

The system should classify the task as comparison/decision support, choose a structured comparison response strategy, generate an answer, run a quality check, and print the final result.

For an ambiguous prompt, the system should ask a useful follow-up question.

Example:

```bash
prompt-orchestrator run "Make this better"
```

Because no target text was provided, the system should return a clarification request instead of inventing content.

For a high-stakes prompt, the system should use a cautious strategy.

Example:

```bash
prompt-orchestrator run "Should I put all my savings into this stock?"
```

The system should classify this as financial/high-stakes decision support and produce cautious, non-prescriptive guidance.

## Development Philosophy

- Build the smallest working pipeline first.
- Keep each milestone testable.
- Use deterministic rules before LLM-based routing.
- Keep model calls behind interfaces.
- Tests must not require live model endpoints.
- Favor simple Python modules over heavy frameworks.
- Make decisions explicit and serializable.
- Keep the output traceable: classification, strategy, prompt plan, generation, quality check, final response.

## Repository Layout Target

The implementation should use a Python `src/` layout:

```text
prompt-orchestrator/
  README.md
  AGENTS.md
  MVP.md
  CHECKPOINTS.md
  ARCHITECTURE.md
  pyproject.toml
  src/
    prompt_orchestrator/
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
  tests/
    test_*.py
  examples/
    *.json
```

Codex may create additional modules if justified, but it should not add unnecessary subsystems.

## Completion Definition

The MVP is complete when:

- All checkpoints in `CHECKPOINTS.md` are implemented.
- The CLI exposes classify, plan, and run behavior.
- The pipeline works using a mock model client.
- Unit tests cover the major routing, classification, clarification, strategy, prompt-building, generation, quality-check, and finalization behavior.
- No RAG, tools, web UI, database, or multi-user server has been added.
