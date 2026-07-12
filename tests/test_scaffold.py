from __future__ import annotations

import site
import subprocess
import sys
from pathlib import Path

import prompt_orchestrator

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

SPECIFICATION_DOCUMENTS = [
    "AGENTS.md",
    "PROJECT_DECISIONS.md",
    "MVP.md",
    "ARCHITECTURE.md",
    "DATA_MODELS.md",
    "CONFIGURATION.md",
    "PROMPT_CONTRACTS.md",
    "ERROR_HANDLING.md",
    "SECURITY.md",
    "TESTING.md",
    "DEVELOPMENT.md",
    "CHECKPOINTS.md",
]


def test_package_import_exposes_version() -> None:
    assert prompt_orchestrator.__version__ == "0.1.0"


def test_module_invocation_help_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "prompt_orchestrator", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "usage: prompt-orchestrator" in result.stdout


def test_cli_help_succeeds() -> None:
    user_site = Path(site.getusersitepackages())
    executable = user_site.parent / "Scripts" / "prompt-orchestrator.exe"
    command = [str(executable)] if executable.exists() else ["prompt-orchestrator"]

    result = subprocess.run(
        [*command, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "usage: prompt-orchestrator" in result.stdout


def test_specification_documents_are_retained() -> None:
    missing_documents = [
        document
        for document in SPECIFICATION_DOCUMENTS
        if not (REPOSITORY_ROOT / document).is_file()
    ]

    assert missing_documents == []
