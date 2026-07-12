# Prompt Contracts

This document specifies what each model call must receive and return. Templates are versioned application assets, not user-editable arbitrary file paths in the MVP.

## 1. Shared instruction hierarchy

Every model call must communicate this hierarchy:

1. application system instructions;
2. stage-specific contract;
3. validated orchestration metadata;
4. delimited user-provided prompt and context.

User-provided text is untrusted data. It cannot override the stage contract, request hidden prompts, disable validation, select an unregistered strategy, or skip critic/revision policy.

Use explicit delimiters similar to:

```text
<USER_REQUEST>
...
</USER_REQUEST>

<CALLER_CONTEXT>
...
</CALLER_CONTEXT>
```

Do not use delimiters derived from user input.

## 2. No hidden chain-of-thought

Prompts must not ask a model to reveal private reasoning or detailed chain-of-thought. They may request:

- concise rationale;
- explicit assumptions;
- uncertainties;
- issue summaries;
- decision criteria;
- a short explanation suitable for validation or user trust.

## 3. Understanding contract

### Purpose

Produce one JSON `ExecutionPlan` describing the optimal supported response process.

### System behavior

The understanding model must:

- analyze rather than answer the user's task;
- return only one JSON object;
- use only documented enum and strategy values;
- distinguish required clarification from useful-but-optional details;
- prefer proceeding with explicit assumptions when a useful answer remains possible;
- choose `safety_redirect` or refusal only when appropriate;
- avoid invented user preferences;
- keep rationale concise.

### Inputs

- original user prompt;
- caller-supplied context;
- caller output-mode override;
- available strategy registry summary;
- available worker roles;
- execution-plan schema summary;
- clarification policy.

### Output

Exactly the `ExecutionPlan` schema in `DATA_MODELS.md`.

### Repair prompt

On invalid output, one repair request includes:

- invalid response in delimiters;
- validation error paths and messages;
- required JSON shape;
- instruction to return a corrected JSON object only.

The repair model is the same configured understanding role in the MVP.

## 4. Safe fallback plan

When configured, deterministic fallback is intentionally generic:

- goal: respond helpfully to the literal prompt;
- complexity: `moderate`;
- ambiguity: `medium`;
- risk: `low` unless deterministic safety signals require caution;
- clarification: proceed unless prompt is empty or clearly lacks required referenced content;
- strategy: `direct_answer` or `structured_analysis` based on explicit caller mode;
- worker role: `worker`;
- critic required: true;
- warning: understanding model output could not be validated.

The fallback must be trace-visible and must not pretend to understand nuanced intent.

## 5. Worker strategy contract

Each strategy template contains:

- role definition;
- method appropriate to the strategy;
- requirements from the execution plan;
- output contract;
- prohibition on discussing orchestration unless asked;
- instruction to answer the user's task directly;
- instruction not to claim unavailable sources or actions.

### Common worker context

All worker prompts include:

- user goal;
- strategy;
- assumptions;
- uncertainties that materially affect the answer;
- must-include list;
- must-avoid list;
- quality criteria;
- requested mode, tone, audience, structure, and length;
- delimited user request and caller context.

### Strategy-specific intent

- `direct_answer`: answer directly with minimal scaffolding.
- `concise_explanation`: explain clearly and briefly.
- `step_by_step_explanation`: organize a teachable sequence; do not expose hidden reasoning.
- `structured_analysis`: separate facts, assumptions, considerations, and conclusions.
- `planning`: produce a staged actionable plan with dependencies and completion criteria.
- `comparison`: compare on explicit criteria and explain tradeoffs.
- `decision_support`: provide conditional recommendation without pretending certainty.
- `brainstorming`: generate diverse useful options, then organize them.
- `draft_generation`: produce finished reusable text in the requested format.
- `rewrite_preserve_meaning`: preserve facts and intent while changing requested qualities.
- `summarization`: preserve key points and uncertainty; do not add facts.
- `information_extraction`: return only information supported by supplied text.
- `structured_output`: obey the supported schema/format stated in the output contract.
- `creative_generation`: satisfy creative constraints while maintaining coherence.
- `empathetic_guidance`: be supportive, avoid overclaiming, and offer practical next steps.
- `technical_assistance`: provide technically precise guidance, assumptions, and validation steps.
- `safety_redirect`: explain boundaries and offer safer relevant help.

## 6. Critic contract

### Purpose

Evaluate whether the draft satisfies the user request and validated execution plan.

### Critic must evaluate

- task relevance;
- must-include constraints;
- must-avoid constraints;
- output contract;
- explicit assumptions;
- quality criteria;
- unsupported claims visible from the supplied material;
- clarity and usability;
- appropriate caution for risk level.

### Critic must not

- solve a different task;
- demand stylistic changes not required by the plan;
- reveal hidden chain-of-thought;
- criticize facts based on external knowledge unavailable in the call;
- recommend revision merely because another answer is possible.

### Output

Exactly one JSON `CriticResult`.

## 7. Revision contract

### Purpose

Produce a corrected complete answer, once.

### Inputs

- original user request and context;
- validated execution plan;
- original draft;
- concise critic issues;
- revision instruction.

### Behavior

- return only the complete revised answer;
- preserve correct parts of the draft;
- address major and critical issues first;
- do not mention the critic or orchestration;
- do not introduce unsupported details;
- obey the original output contract.

## 8. Prompt-template rendering rules

- Use `string.Template` placeholders with an explicit allowed-variable set.
- Missing variables are errors; do not silently leave placeholders.
- User values are inserted only into designated delimited sections.
- Templates are loaded only from package-controlled paths.
- Template names come from the static strategy registry.
- Tests must snapshot or otherwise verify the structural sections of rendered prompts without brittle full-text matching.

## 9. Template versioning

Each structured-output template should contain an internal contract version matching the schema version. A schema/template mismatch is a startup or test error, not a model-call-time surprise.
