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

The MVP can:

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
- account for per-call token usage and latency on every run;
- evaluate orchestrated output against a single-call baseline over a corpus,
  with deterministic checks, an optional model judge, and a token/latency cost
  comparison;
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
- [`ROADMAP.md`](ROADMAP.md): future product phases and intended direction.
- [`PROJECT_STATE.md`](PROJECT_STATE.md): current implementation-grounded
  repository state.
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

## Planning and project status

Use [`ROADMAP.md`](ROADMAP.md) for future direction and phase definitions. Use
[`PROJECT_STATE.md`](PROJECT_STATE.md) for the implementation that actually
exists today, including modules, schemas, commands, tests, and known gaps.
[`CHECKPOINTS.md`](CHECKPOINTS.md) remains the historical MVP milestone record.

Planners should read `ROADMAP.md` and `PROJECT_STATE.md` together before
proposing roadmap work so planned capabilities are not confused with current
behavior.

## Installation

Prompt Orchestrator requires Python 3.12 or newer.

```bash
python -m pip install -e ".[dev]"
```

The editable install provides development tools and the `prompt-orchestrator`
console script. You can also run the CLI directly as a module.

## CLI Usage

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

# Evaluate orchestration against a single-call baseline with cost accounting
prompt-orchestrator eval --config config.yaml --corpus examples/eval-corpus.yaml

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

Copy `config.example.yaml` to a local untracked file such as `config.local.yaml`,
then update the model endpoint and model alias. A single local model can serve
all MVP roles:

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

For a ready-to-edit local llama-server example, see
[`examples/config.local-llama.yaml`](examples/config.local-llama.yaml). Prompt
Orchestrator does not start or download models; start your local
OpenAI-compatible server separately.

## Scripted examples

The repository includes no-network examples using the mock scripted provider:

```bash
python -m prompt_orchestrator config validate --config examples/config.scripted.yaml
python -m prompt_orchestrator understand --config examples/config.scripted.yaml "Help me choose between SQLite and PostgreSQL"
python -m prompt_orchestrator plan --config examples/config.scripted.yaml "Help me choose between SQLite and PostgreSQL"
python -m prompt_orchestrator run --config examples/config.scripted.yaml "Help me choose between SQLite and PostgreSQL"
python -m prompt_orchestrator run --config examples/config.scripted.yaml --json "Help me choose between SQLite and PostgreSQL"
python -m prompt_orchestrator run --config examples/config.scripted.yaml --trace "Help me choose between SQLite and PostgreSQL"
Get-Content examples/request.txt | python -m prompt_orchestrator run --config examples/config.scripted.yaml --stdin
```

See [`examples/README.md`](examples/README.md) for the example files and local
server notes.

## Architecture overview

The runtime is a synchronous CLI pipeline:

```text
PromptRequest
  -> intake normalization
  -> understanding role produces ExecutionPlan JSON
  -> deterministic schema and policy validation
  -> clarification/refusal gate or worker prompt planning
  -> worker generation
  -> critic review
  -> optional one-pass revision
  -> final response and optional trace
```

Configuration maps roles to named models, and named models to providers. The
pipeline asks for roles, not URLs or provider-specific payloads.

## Troubleshooting

- If `prompt-orchestrator` is not found, use
  `python -m prompt_orchestrator ...` or add your Python Scripts directory to
  `PATH`.
- If `config validate` reports a missing configuration, pass `--config` or
  create `config.local.yaml` in the repository root.
- If a local model call fails, verify that your OpenAI-compatible server is
  running, the `base_url` ends at `/v1`, and the configured model alias matches
  the server.
- API keys should be referenced by environment-variable name in YAML. Do not put
  real secret values in committed config files. Put private HTTP header values
  under `secret_headers`, not `default_headers`.

## MVP completion checklist

- Configuration validation works for mock and OpenAI-compatible providers.
- The documented CLI commands are implemented: `config validate`, `understand`,
  `plan`, and `run`.
- The complete pipeline runs with scripted model responses and no network.
- A local OpenAI-compatible endpoint can be configured with one model mapped to
  all roles.
- Understanding and critic outputs are parsed as structured JSON and validated
  before use.
- Clarification and refusal stop before worker execution.
- Critic-triggered revision is bounded to one pass.
- Structured-output repair, transient HTTP retry, and revision attempts are
  bounded by configuration.
- Traces are in-memory, optional, and sanitized.
- Default CLI output prints only the final answer or clarification question.
- Live smoke testing is opt-in with `pytest -m live`.
- The MVP intentionally excludes RAG, tools, memory, databases, service mode,
  web UI, streaming, and automatic API escalation.

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
