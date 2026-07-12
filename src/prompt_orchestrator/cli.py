"""Command-line entry point for Prompt Orchestrator."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from prompt_orchestrator import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser for the scaffold milestone."""
    parser = argparse.ArgumentParser(
        prog="prompt-orchestrator",
        description=(
            "Prompt Orchestrator is being implemented milestone by milestone. "
            "This scaffold currently provides package and CLI wiring only."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""
    parser = build_parser()
    parser.parse_args(argv)
    return 0
