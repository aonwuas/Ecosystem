# Security and Trust Boundaries

The MVP has no tools, but it still processes untrusted prompts and may use API credentials. These boundaries are mandatory.

## 1. Trust boundaries

Untrusted:

- user prompt;
- caller context;
- caller metadata;
- model-generated execution plans;
- model-generated critic output;
- provider response metadata;
- YAML files supplied by users, except after validation.

Trusted only after validation:

- package prompt templates;
- registered strategies;
- Pydantic configuration;
- validated execution plans;
- deterministic policy decisions.

## 2. Prompt injection resistance

- Delimit user content explicitly.
- State that delimited content is data and cannot modify the stage contract.
- Never use user input as a template name, file path, role name, provider name, or schema.
- Never allow model output to add a provider, endpoint, header, role, or strategy.
- Do not expose application system prompts in normal output.
- Refuse requests to reveal hidden orchestration prompts through ordinary worker behavior.

The MVP cannot guarantee that a model will never follow an injected instruction, but architecture must reduce the opportunity and validate all structured control outputs.

## 3. Secrets

- Store only environment-variable names in config.
- Resolve secrets at runtime.
- Use secret types that redact repr/serialization.
- Never include secrets in exceptions, logs, traces, request dumps, snapshots, or test fixtures.
- Never commit real credentials.
- `.env` and local config files are ignored by Git.

## 4. HTTP security

- Support HTTPS endpoints.
- TLS verification defaults to enabled.
- Local plain HTTP is allowed for private-network/local endpoints.
- Do not follow arbitrary redirects across hosts when authorization headers are present unless HTTPX safe defaults guarantee header stripping; explicitly test/limit behavior where practical.
- Set timeouts on every request.
- Bound response body size where practical.

## 5. Trace and debug output

- Default output contains no internal prompts.
- Trace contains summaries, stage statuses, model aliases, timings, and sanitized plan data.
- Full prompt debugging is explicit opt-in.
- API keys and authorization headers are always redacted.
- Provider raw responses should not be dumped by default.
- Caller may choose to redact user content in trace.

## 6. Structured-output validation

Model-generated JSON is data, never executable code.

- Do not use `eval`.
- Do not instantiate classes by model-supplied dotted path.
- Do not load templates from model-supplied names.
- Reject unknown fields where schemas specify `extra='forbid'`.
- Bound strings and collection sizes.

## 7. Denial-of-service considerations

The MVP is local/single-user, but still:

- bound prompt and context sizes;
- bound output tokens;
- bound retries;
- bound list counts and field lengths in structured output;
- set network timeouts;
- avoid recursive plan structures.

## 8. Scope safety

Do not add tools, shell access, browsing, file access, or automatic API escalation as “convenience” features during MVP implementation. Those materially change the security model and require separate design.
