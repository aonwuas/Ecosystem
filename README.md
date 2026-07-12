# Prompt Orchestrator

Prompt Orchestrator is a CLI-first runtime that improves LLM responses by separating **task understanding**, **execution planning**, **answer generation**, and **quality review** into explicit stages.

The MVP is intentionally limited to model orchestration. It does not use retrieval-augmented generation, external tools, web browsing, persistent memory, or a web interface.

## Product thesis

A capable model often performs better when it is not asked to infer the task, choose a response method, solve the task, and evaluate its own work in one unstructured generation.

Prompt Orchestrator instead uses this flow:

```text
User prompt
    ↓
Understanding model
    ↓
Validated ExecutionPlan
    ↓
Worker model
    ↓
Critic model
    ↓
Optional one-pass revision
    ↓
Final response
```

The roles may use separate models or all point to the same model. Models may be hosted locally through an OpenAI-compatible server such as `llama-server`, or later through a hosted API.

## MVP capabilities

At completion, the product will:

- accept a prompt from the CLI or standard input;
- normalize the request and preserve conversation context supplied by the caller;
- ask an understanding model to produce a structured `ExecutionPlan`;
- validate that plan against deterministic schemas and policy rules;
- decide whether clarification is required;
- select a bounded response strategy and configured model role;
- build an internal worker prompt;
- generate a draft answer;
- run a critic pass against explicit quality criteria;
- perform at most one revision pass;
- return the final answer;
- optionally expose a structured trace of the orchestration process;
- support mock models for deterministic tests;
- support OpenAI-compatible HTTP model endpoints through configuration.

## Explicit non-goals

The MVP does **not** include:

- RAG or vector databases;
- filesystem, shell, browser, email, calendar, or other tools;
- autonomous agents that take actions;
- persistent memory or conversation storage;
- a database;
- a web UI;
- multi-user service mode;
- automatic provider escalation based on cost or model quality;
- hidden chain-of-thought capture or display.

## Repository instruction files

The repository is governed by the following documents:

- [`AGENTS.md`](AGENTS.md): mandatory rules for Codex and other coding agents.
- [`MVP.md`](MVP.md): product scope and acceptance criteria.
- [`PROJECT_DECISIONS.md`](PROJECT_DECISIONS.md): fixed implementation decisions for the MVP.
- [`ARCHITECTURE.md`](ARCHITECTURE.md): system boundaries and component interactions.
- [`DATA_MODELS.md`](DATA_MODELS.md): canonical schemas and enums.
- [`CONFIGURATION.md`](CONFIGURATION.md): model-provider and runtime configuration.
- [`PROMPT_CONTRACTS.md`](PROMPT_CONTRACTS.md): contracts for each model call.
- [`ERROR_HANDLING.md`](ERROR_HANDLING.md): retries, fallbacks, and failure semantics.
- [`SECURITY.md`](SECURITY.md): secrets, prompt boundaries, and logging rules.
- [`TESTING.md`](TESTING.md): required test strategy.
- [`DEVELOPMENT.md`](DEVELOPMENT.md): development commands and conventions.
- [`CHECKPOINTS.md`](CHECKPOINTS.md): ordered implementation milestones.
- [`CODEX_INSTRUCTIONS.md`](CODEX_INSTRUCTIONS.md): copy-ready Codex prompts for every milestone.

When documents appear to conflict, use the precedence order in `AGENTS.md`.

## Intended CLI after completion

The CLI supports two equivalent invocation forms:

- `python -m prompt_orchestrator ...`
- `prompt-orchestrator ...` when the Python Scripts directory is on `PATH`

```bash
# Validate configuration
prompt-orchestrator config validate --config config.yaml

# Inspect the model-produced understanding and execution plan
prompt-orchestrator understand "Help me choose between SQLite and PostgreSQL"

# Build the worker prompt without generating an answer
prompt-orchestrator plan "Help me choose between SQLite and PostgreSQL"

# Run the complete pipeline
prompt-orchestrator run "Help me choose between SQLite and PostgreSQL"

# Read a long prompt from stdin
cat request.txt | prompt-orchestrator run --stdin

# Show a structured orchestration trace
prompt-orchestrator run "Draft a project proposal" --trace

# Emit machine-readable output
prompt-orchestrator run "Summarize this text: ..." --json
```

The examples above use the installed console script. If your shell reports that
`prompt-orchestrator` is not found, use `python -m prompt_orchestrator ...`
instead, or add your Python Scripts directory to `PATH`. On Windows, pip may
install the script under a user directory such as
`%APPDATA%\Python\Python312\Scripts` or the matching directory for your Python
version.

## Configuration quick start

Copy `config.example.yaml` to a local untracked file such as `config.local.yaml`, then update the model endpoints.

```yaml
providers:
  local_fast:
    type: openai_compatible
    base_url: http://127.0.0.1:8080/v1
    api_key_env: null

models:
  general_local:
    provider: local_fast
    model: local-model-alias
    temperature: 0.2
    max_output_tokens: 4096
    timeout_seconds: 180

roles:
  understanding: general_local
  worker: general_local
  critic: general_local
  revision: general_local
```

The same configured model may serve every role. Later, each role may be mapped independently to local or hosted models without changing pipeline code.

## Building the repository with Codex

Implement one milestone at a time. The canonical instruction pattern is:

```text
Read AGENTS.md and all project specification files it identifies.
Implement Milestone N from CHECKPOINTS.md only.
Do not implement later milestones.
Run the tests required by the milestone.
Update documentation only where the milestone requires it.
Report files changed, tests run, and unresolved issues, then stop.
```

Copy-ready prompts are provided in `CODEX_INSTRUCTIONS.md`.
