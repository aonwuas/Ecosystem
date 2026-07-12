# Development Guide

## 1. Supported environment

- Python 3.12+
- Windows and Linux
- Git checkout with LF-normalized text files

## 2. Initial setup after Milestone 1

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install editable development dependencies using the mechanism defined in `pyproject.toml`, expected to be:

```bash
python -m pip install -e ".[dev]"
```

## 3. Standard commands

```bash
pytest
ruff check .
ruff format .
mypy src
prompt-orchestrator --help
```

Check formatting without modifying files:

```bash
ruff format --check .
```

## 4. Package conventions

- Use type annotations for public and internal functions where practical.
- Prefer immutable/frozen domain models when mutation is unnecessary.
- Keep I/O at boundaries; domain validation should be testable without network or CLI.
- Use explicit exceptions from `exceptions.py`.
- Use logging for diagnostics, never `print` inside library code.
- CLI renderer owns stdout/stderr formatting.
- Avoid global mutable registries; build or expose read-only registries.
- Keep provider HTTP payload construction inside the provider client.

## 5. Style

- Ruff controls formatting and linting.
- Use descriptive names over abbreviations.
- Keep functions small around stage boundaries.
- Public modules/classes require docstrings when their purpose is not obvious.
- Comments explain why, not restate code.

## 6. Branch and milestone workflow

Recommended:

```text
main
  └── milestone-01-scaffold
  └── milestone-02-domain-models
  ...
```

Each milestone should produce a reviewable commit or pull request. Do not combine unrelated cleanup with milestone behavior.

## 7. Configuration for local use

Copy:

```bash
cp config.example.yaml config.local.yaml
```

`config.local.yaml` is ignored by Git. Update URLs and model aliases for local llama-server instances.

## 8. Logging

Library modules use Python logging. Default CLI operation should remain quiet except for the requested answer. `--trace` or debug flags enable more detail.

## 9. Versioning

The MVP begins at an unreleased `0.1.0` development version. Do not publish packages as part of the MVP milestones unless explicitly instructed.
