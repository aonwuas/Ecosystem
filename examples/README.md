# Examples

Run these commands from the repository root after installing the package with:

```bash
python -m pip install -e ".[dev]"
```

Use either invocation form:

- `python -m prompt_orchestrator ...`
- `prompt-orchestrator ...` when the Python Scripts directory is on `PATH`

## Scripted No-Network Run

The scripted configuration uses `examples/scripted-basic.yaml`, so these
commands do not call a live model server.

```bash
python -m prompt_orchestrator config validate --config examples/config.scripted.yaml
python -m prompt_orchestrator understand --config examples/config.scripted.yaml "Help me choose between SQLite and PostgreSQL"
python -m prompt_orchestrator plan --config examples/config.scripted.yaml "Help me choose between SQLite and PostgreSQL"
python -m prompt_orchestrator run --config examples/config.scripted.yaml "Help me choose between SQLite and PostgreSQL"
python -m prompt_orchestrator run --config examples/config.scripted.yaml --json "Help me choose between SQLite and PostgreSQL"
python -m prompt_orchestrator run --config examples/config.scripted.yaml --trace "Help me choose between SQLite and PostgreSQL"
```

Standard input works too:

PowerShell:

```powershell
Get-Content examples/request.txt | python -m prompt_orchestrator run --config examples/config.scripted.yaml --stdin
```

Bash:

```bash
cat examples/request.txt | python -m prompt_orchestrator run --config examples/config.scripted.yaml --stdin
```

## Local Llama-Server Config

`examples/config.local-llama.yaml` maps all four roles to one
OpenAI-compatible endpoint at `http://127.0.0.1:8080/v1`. Update `base_url` and
`model` to match your local server, then run:

```bash
python -m prompt_orchestrator config validate --config examples/config.local-llama.yaml
python -m prompt_orchestrator run --config examples/config.local-llama.yaml "Create a practical study plan for learning linear algebra"
```

Prompt Orchestrator does not start or download models. Start your local model
server separately.

## Troubleshooting

If `prompt-orchestrator` is not found, use `python -m prompt_orchestrator` or
add your Python Scripts directory to `PATH`. On Windows, pip often installs
console scripts under a path like `%APPDATA%\Python\Python312\Scripts`, adjusted
for the Python version you are using.
