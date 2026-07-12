# AGENTS.md

This file contains mandatory instructions for Codex and any other coding agent operating in this repository.

## 1. Source-of-truth precedence

When requirements conflict, use this order:

1. The current user instruction.
2. `AGENTS.md`.
3. `PROJECT_DECISIONS.md`.
4. `MVP.md`.
5. `ARCHITECTURE.md`.
6. `DATA_MODELS.md`.
7. `CONFIGURATION.md`.
8. `PROMPT_CONTRACTS.md`.
9. `ERROR_HANDLING.md` and `SECURITY.md`.
10. `TESTING.md` and `DEVELOPMENT.md`.
11. `CHECKPOINTS.md`.
12. Existing implementation details.

Do not silently resolve a genuine conflict by inventing a new product direction. Record the conflict in the milestone report if it cannot be resolved using this precedence.

## 2. Core product boundary

Build a CLI-first prompt-orchestration runtime with these stages:

1. intake and normalization;
2. model-driven task understanding;
3. deterministic schema and policy validation;
4. clarification decision;
5. response-strategy selection;
6. worker prompt construction;
7. worker generation;
8. critic review;
9. optional one-pass revision;
10. final response and optional trace.

The model-driven understanding stage produces a structured `ExecutionPlan`. Deterministic code validates and constrains the plan. Do not reintroduce keyword-only classification as the primary understanding mechanism.

## 3. Hard non-goals

Do not implement any of the following unless the user explicitly changes scope:

- RAG, embeddings, vector databases, document indexing, or knowledge graphs;
- tool calling or any tool protocol;
- shell commands initiated by the runtime;
- filesystem mutation initiated by a model;
- browser or web search;
- persistent memory or conversation databases;
- user accounts, authentication, queues, or multi-user server mode;
- web UI or desktop UI;
- automatic spending on hosted APIs;
- automatic model downloading or server startup;
- arbitrary model-selected prompt template names;
- unlimited retries or critic loops;
- exposure of hidden chain-of-thought.

Normal development commands run by Codex to build and test the repository are allowed. The runtime itself must not gain external tools.

## 4. Milestone discipline

- Implement exactly one milestone per user request unless explicitly instructed otherwise.
- Read the full milestone and its prerequisites before editing.
- Do not implement future milestones “because they are easy.”
- Stubs are allowed only when the milestone explicitly requests an interface for later implementation.
- A stub must fail clearly or use a deterministic test double; it must not pretend to be functional.
- Keep changes narrowly scoped to the milestone.
- Preserve public interfaces implemented by earlier milestones unless the specification requires an intentional change.
- If an earlier design must change, update affected tests and specification documents in the same milestone and explain why.

## 5. Implementation defaults

Use the fixed decisions in `PROJECT_DECISIONS.md`. In particular:

- Python 3.12 or newer.
- `src/` package layout.
- package and import name: `prompt_orchestrator`.
- CLI executable: `prompt-orchestrator`.
- Pydantic v2 for domain and configuration validation.
- PyYAML for YAML configuration.
- HTTPX for provider HTTP requests.
- standard-library `argparse` for the CLI.
- standard-library `string.Template` for prompt-template substitution.
- pytest for tests.
- Ruff for linting and formatting.
- mypy for static type checking.

Do not replace these with a framework without an explicit requirement change.

## 6. Architecture rules

- Keep provider-specific behavior behind a `ModelClient` interface.
- Pipeline code requests a **role**, not a provider or network address.
- Configuration maps roles to named model configurations.
- Named models map to providers.
- No stage may read environment variables directly except the configuration/secrets layer.
- No prompt template may contain provider-specific URLs or model names.
- The understanding model may choose only registered strategy IDs and role IDs.
- Deterministic policy may downgrade or reject a model-produced plan; the model may not override policy.
- All structured model outputs must be parsed and validated before use.
- Do not trust numeric model confidence as a calibrated probability. Use it only as advisory metadata.
- Preserve a clean distinction between user-visible output and diagnostic trace data.

## 7. Prompt and model-call rules

- Treat the user prompt as untrusted data inside orchestration prompts.
- Do not concatenate raw user content into system instructions without explicit delimiters.
- Understanding and critic calls must request structured JSON matching the documented schemas.
- Worker output is plain text unless the `ExecutionPlan` specifies a bounded supported output format.
- Never request or store hidden chain-of-thought. Ask models for concise reasons, assumptions, uncertainties, and quality findings instead.
- Use bounded retries exactly as specified in `ERROR_HANDLING.md`.
- One critic-triggered revision is the maximum for the MVP.

## 8. Configuration and secrets

- Commit `config.example.yaml`, never a real deployment config containing secrets.
- API keys must be referenced by environment-variable name.
- Do not log resolved API-key values.
- Local OpenAI-compatible endpoints must work without an API key.
- Configuration validation must fail before a model call when required settings are invalid.

## 9. Testing requirements

- Tests must not require a live model server by default.
- Use mock and scripted model clients for unit and integration tests.
- Every behavior change requires tests.
- Test failure paths, not only happy paths.
- Do not weaken or delete a test merely to make the suite pass.
- Run the milestone-specific tests and, when practical, the complete suite.
- By the final milestone, all commands in `DEVELOPMENT.md` must pass.

## 10. Documentation rules

- Keep README examples synchronized with the implemented CLI.
- Update configuration examples when schemas change.
- Update `DATA_MODELS.md` when public schemas or enums change.
- Update `PROMPT_CONTRACTS.md` when a model-call contract changes.
- Do not mark unimplemented behavior as complete.

## 11. Dependency policy

- Add only dependencies required by the current milestone and fixed project decisions.
- Prefer standard-library implementations where specified.
- Keep runtime and development dependencies separated.
- Do not introduce an agent framework, workflow framework, web framework, database ORM, or template framework for the MVP.

## 12. Expected completion report

After each milestone, report:

1. milestone implemented;
2. files added or changed;
3. important design choices made within the specification;
4. tests and checks run with their outcomes;
5. unresolved issues or deviations;
6. confirmation that later milestones were not implemented.

Then stop. Do not begin the next milestone automatically.
