"""Command-line entry point for Prompt Orchestrator."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from prompt_orchestrator import __version__
from prompt_orchestrator.config import load_config, summarize_config
from prompt_orchestrator.exceptions import ConfigurationError


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""
    parser = argparse.ArgumentParser(
        prog="prompt-orchestrator",
        description=(
            "Prompt Orchestrator is being implemented milestone by milestone. "
            "This build currently provides configuration validation."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")

    config_parser = subparsers.add_parser(
        "config",
        help="Configuration commands.",
    )
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    validate_parser = config_subparsers.add_parser(
        "validate",
        help="Validate a YAML configuration file.",
    )
    validate_parser.add_argument(
        "--config",
        help="Path to a YAML configuration file.",
    )
    validate_parser.set_defaults(handler=_handle_config_validate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        return 0
    try:
        return int(handler(args))
    except ConfigurationError as exc:
        print(f"Error [{exc.code}]: {exc}", file=sys.stderr)
        return 2


def _handle_config_validate(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    summary = summarize_config(config)
    print("Configuration valid.")
    print(f"Path: {summary.path}")
    print(f"Providers: {', '.join(summary.providers)}")
    print(f"Models: {', '.join(summary.models)}")
    print("Roles:")
    for role, model_name in summary.roles.items():
        print(f"  {role}: {model_name}")
    return 0
