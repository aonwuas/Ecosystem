# Configuration Specification

## 1. Goals

Configuration must make model location and provider type independent from pipeline code. It must support local OpenAI-compatible servers now and compatible hosted APIs later.

The runtime configuration is YAML.

## 2. Top-level structure

```yaml
version: 1
providers: {}
models: {}
roles: {}
runtime: {}
```

Unknown top-level keys are rejected by default so configuration mistakes do not silently pass.

## 3. Providers

A provider describes transport and authentication, not sampling behavior.

### OpenAI-compatible provider

```yaml
providers:
  local_ai_pc:
    type: openai_compatible
    base_url: http://192.168.1.20:8080/v1
    api_key_env: null
    default_headers: {}
    verify_tls: true
```

Fields:

- `type`: required; `openai_compatible` or `mock` in the MVP.
- `base_url`: required for `openai_compatible`; normalized without a trailing slash.
- `api_key_env`: optional environment-variable name. The value is resolved at runtime and never included in serialized config or traces.
- `default_headers`: optional string-to-string map. Header values must not be used for secrets in committed config.
- `verify_tls`: optional boolean, default `true`. Local HTTP endpoints are allowed; disabling TLS verification should emit a warning for HTTPS.

### Mock provider

```yaml
providers:
  scripted:
    type: mock
    fixture_path: tests/fixtures/scripted_models.yaml
```

The mock provider is primarily for tests and examples.

## 4. Named models

A named model references a provider and contains generation defaults.

```yaml
models:
  qwen_understanding:
    provider: local_ai_pc
    model: qwen-model-alias
    temperature: 0.1
    max_output_tokens: 3000
    timeout_seconds: 180
    extra_body: {}
    metadata:
      speed_tier: medium
      quality_tier: standard
      cost_tier: local
```

Required fields:

- `provider`
- `model`

Optional fields and defaults:

- `temperature`: default `0.2`, range `0.0` to `2.0`.
- `max_output_tokens`: default `4096`, positive bounded integer.
- `timeout_seconds`: default `180`, positive bounded integer.
- `extra_body`: optional JSON-compatible map forwarded only by the provider adapter.
- `metadata`: advisory values for display/future routing; the MVP does not automatically choose by tier.

Configuration does not manage model context size or server startup. Those remain llama-server/provider concerns.

## 5. Role bindings

```yaml
roles:
  understanding: qwen_understanding
  worker: qwen_worker
  critic: qwen_reviewer
  revision: qwen_worker
```

Rules:

- all four MVP roles are required;
- values must reference named models;
- multiple roles may reference the same model;
- model-produced plans may select only a configured role permitted by the strategy/policy;
- the understanding role normally selects `worker`; specialist roles are future scope unless added to the fixed schema.

## 6. Runtime settings

```yaml
runtime:
  structured_output_repair_attempts: 1
  transient_http_retries: 1
  enable_critic: true
  strict_critic: false
  enable_revision: true
  max_revision_attempts: 1
  understanding_failure_mode: error
  default_output_mode: text
  trace:
    enabled_by_default: false
    include_prompt_summaries: true
    include_full_prompts: false
    redact_user_content: false
```

Validation rules:

- repair attempts: `0` or `1` in the MVP;
- transient retries: `0` or `1` in the MVP;
- max revision attempts: `0` or `1`;
- `understanding_failure_mode`: `error` or `safe_fallback`;
- `default_output_mode`: `text` or `json`;
- full prompt tracing defaults to false;
- secret values are always redacted regardless of trace configuration.

## 7. Strategy policy overrides

The MVP may support bounded overrides:

```yaml
runtime:
  strategy_overrides:
    creative_generation:
      enable_critic: false
    safety_redirect:
      enable_revision: false
```

Only known override fields are accepted. Config cannot provide arbitrary prompt-template paths in the MVP.

## 8. Configuration search order

When `--config` is absent, use this order:

1. path in `PROMPT_ORCHESTRATOR_CONFIG`;
2. `./config.local.yaml`;
3. `./config.yaml`;
4. fail with a clear configuration-not-found error.

Do not search arbitrary user directories in the MVP.

## 9. Environment variables

Only names are stored in YAML:

```yaml
api_key_env: OPENAI_API_KEY
```

At load time:

- resolve the environment variable;
- fail if it is required but missing;
- wrap the value in a secret type;
- exclude it from repr, JSON, logs, and traces.

## 10. Example complete configuration

See `config.example.yaml`.

## 11. Validation command

```bash
python -m prompt_orchestrator config validate --config config.local.yaml
```

Successful validation should summarize provider names, model names, and role bindings without printing secrets.

The installed `prompt-orchestrator` console script supports the same arguments
when the Python Scripts directory is on `PATH`.

## 12. Future provider compatibility

The schema should allow future provider adapters without changing role resolution. Future provider-specific fields belong in discriminated provider models, not in pipeline code.
