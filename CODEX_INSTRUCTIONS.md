# Copy-Ready Codex Instructions

Use one instruction at a time. Start each instruction in the repository root. Do not ask Codex to implement all milestones in one run.

## Milestone 1

```text
Read AGENTS.md and every specification document it identifies.
Implement Milestone 1 from CHECKPOINTS.md only: Repository scaffold and developer tooling.
Do not implement later milestones.
Run the milestone acceptance checks.
Report files changed, checks run, unresolved issues, and confirm that later milestones were not implemented. Then stop.
```

Completion: installable Python scaffold, CLI help, tests, lint/format/type-check configuration.

## Milestone 2

```text
Read AGENTS.md and every specification document it identifies.
Implement Milestone 2 from CHECKPOINTS.md only: Canonical domain models and enums.
Do not implement later milestones.
Run the milestone acceptance checks.
Report files changed, checks run, unresolved issues, and confirm that later milestones were not implemented. Then stop.
```

Completion: strict Pydantic request, execution-plan, model-response, critic, final-response, and trace schemas.

## Milestone 3

```text
Read AGENTS.md and every specification document it identifies.
Implement Milestone 3 from CHECKPOINTS.md only: YAML configuration and role resolution.
Do not implement later milestones.
Run the milestone acceptance checks.
Report files changed, checks run, unresolved issues, and confirm that later milestones were not implemented. Then stop.
```

Completion: validated provider/model/role/runtime config, secret resolution, and `config validate`.

## Milestone 4

```text
Read AGENTS.md and every specification document it identifies.
Implement Milestone 4 from CHECKPOINTS.md only: Model client abstraction and provider adapters.
Do not implement later milestones.
Run the milestone acceptance checks.
Report files changed, checks run, unresolved issues, and confirm that later milestones were not implemented. Then stop.
```

Completion: mock/scripted clients plus OpenAI-compatible HTTP model client with bounded retries.

## Milestone 5

```text
Read AGENTS.md and every specification document it identifies.
Implement Milestone 5 from CHECKPOINTS.md only: Structured-output extraction and validation.
Do not implement later milestones.
Run the milestone acceptance checks.
Report files changed, checks run, unresolved issues, and confirm that later milestones were not implemented. Then stop.
```

Completion: robust extraction and schema validation for model-produced JSON plus repair diagnostics.

## Milestone 6

```text
Read AGENTS.md and every specification document it identifies.
Implement Milestone 6 from CHECKPOINTS.md only: Strategy registry and prompt-template system.
Do not implement later milestones.
Run the milestone acceptance checks.
Report files changed, checks run, unresolved issues, and confirm that later milestones were not implemented. Then stop.
```

Completion: bounded strategy registry and safe templates for understanding, worker, critic, and revision calls.

## Milestone 7

```text
Read AGENTS.md and every specification document it identifies.
Implement Milestone 7 from CHECKPOINTS.md only: Intake and understanding stage.
Do not implement later milestones.
Run the milestone acceptance checks.
Report files changed, checks run, unresolved issues, and confirm that later milestones were not implemented. Then stop.
```

Completion: prompt intake, model-driven execution-plan generation, one repair attempt, and configured fallback/error path.

## Milestone 8

```text
Read AGENTS.md and every specification document it identifies.
Implement Milestone 8 from CHECKPOINTS.md only: Deterministic execution-plan policy and clarification gate.
Do not implement later milestones.
Run the milestone acceptance checks.
Report files changed, checks run, unresolved issues, and confirm that later milestones were not implemented. Then stop.
```

Completion: trusted policy layer that constrains model plans and decides proceed, clarify, or redirect.

## Milestone 9

```text
Read AGENTS.md and every specification document it identifies.
Implement Milestone 9 from CHECKPOINTS.md only: Worker prompt planning and generation stage.
Do not implement later milestones.
Run the milestone acceptance checks.
Report files changed, checks run, unresolved issues, and confirm that later milestones were not implemented. Then stop.
```

Completion: validated plan becomes a strategy-specific worker prompt and draft answer; plan-only operation works.

## Milestone 10

```text
Read AGENTS.md and every specification document it identifies.
Implement Milestone 10 from CHECKPOINTS.md only: Critic and one-pass revision stages.
Do not implement later milestones.
Run the milestone acceptance checks.
Report files changed, checks run, unresolved issues, and confirm that later milestones were not implemented. Then stop.
```

Completion: structured critic review and at most one bounded revision, with clear degradation behavior.

## Milestone 11

```text
Read AGENTS.md and every specification document it identifies.
Implement Milestone 11 from CHECKPOINTS.md only: Pipeline runner, state machine, finalizer, and trace.
Do not implement later milestones.
Run the milestone acceptance checks.
Report files changed, checks run, unresolved issues, and confirm that later milestones were not implemented. Then stop.
```

Completion: complete library-level orchestration pipeline and sanitized in-memory trace.

## Milestone 12

```text
Read AGENTS.md and every specification document it identifies.
Implement Milestone 12 from CHECKPOINTS.md only: Complete CLI and output rendering.
Do not implement later milestones.
Run the milestone acceptance checks.
Report files changed, checks run, unresolved issues, and confirm that later milestones were not implemented. Then stop.
```

Completion: usable `config validate`, `understand`, `plan`, and `run` commands with text, JSON, stdin, and trace modes.

## Milestone 13

```text
Read AGENTS.md and every specification document it identifies.
Implement Milestone 13 from CHECKPOINTS.md only: Examples, optional live smoke test, and documentation synchronization.
Do not implement later milestones.
Run the milestone acceptance checks.
Report files changed, checks run, unresolved issues, and confirm that later milestones were not implemented. Then stop.
```

Completion: local llama-server examples, deterministic scripted examples, opt-in live smoke test, and synchronized documentation.

## Milestone 14

```text
Read AGENTS.md and every specification document it identifies.
Implement Milestone 14 from CHECKPOINTS.md only: Hardening and MVP completion audit.
Do not add new product scope.
Specifically do not add RAG, tools, memory, databases, service mode, web UI, streaming, or automatic API escalation.
Run every final quality gate and fix issues within MVP scope.
Report files changed, checks run, remaining limitations, and the MVP completion audit. Then stop.
```

Completion: quality gates pass, redaction/retry/policy behavior is audited, scope remains clean, and the repository is ready for real local-model testing.
