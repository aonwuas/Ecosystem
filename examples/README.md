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

## Evaluation (orchestration vs fair controls)

`examples/config.eval-scripted.yaml` and `examples/eval-corpus.yaml` run the
evaluation harness with no network. Each case runs through the full pipeline
(the treatment) and through a single-call control on the same worker model, with
token and latency cost accounted for each arm:

```bash
python -m prompt_orchestrator eval --config examples/config.eval-scripted.yaml --corpus examples/eval-corpus.yaml
python -m prompt_orchestrator eval --config examples/config.eval-scripted.yaml --corpus examples/eval-corpus.yaml --json
python -m prompt_orchestrator eval --config examples/config.eval-scripted.yaml --corpus examples/eval-corpus.yaml --arms none
```

The report shows, per arm, the deterministic pass rate with a 95% Wilson
confidence interval, the token/latency cost, the compute ratio versus the
treatment, and quality-per-1k-tokens — so orchestration's quality can be weighed
against its cost. Deterministic checks (`must_include`, `must_avoid`, length,
expected status) run without a model.

**Equal-compute controls** — `--arms best_of_n,self_refine` (with `--best-of-n N`)
and `--ablations` — are the fairest test: they spend a comparable token budget a
different way, so a win is attributable to structure, not spend. The scripted
example only scripts the single-call control; running the other arms or the
pairwise judge (`--judge`, which judges both orders) needs a live model or a
matching scripted fixture (see `tests/test_cli_eval.py` for the exact call
sequence per arm).

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
