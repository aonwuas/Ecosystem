"""Command-line entry point for Prompt Orchestrator."""

from __future__ import annotations

import argparse
import sys
import traceback
from collections.abc import Callable, Sequence

from prompt_orchestrator import __version__
from prompt_orchestrator.clients import create_pipeline_client
from prompt_orchestrator.config import load_config, summarize_config
from prompt_orchestrator.config.models import PromptOrchestratorConfig
from prompt_orchestrator.domain import PromptRequest
from prompt_orchestrator.domain.enums import OutputMode
from prompt_orchestrator.domain.trace import Trace
from prompt_orchestrator.exceptions import (
    ConfigurationError,
    InputError,
    PromptOrchestratorError,
    ProviderError,
)
from prompt_orchestrator.pipeline import PipelinePlanResult, PipelineRunner
from prompt_orchestrator.rendering import (
    render_final_text,
    render_json,
    render_plan_text,
    render_understand_text,
)
from prompt_orchestrator.stages import run_understanding_stage


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""
    parser = argparse.ArgumentParser(
        prog="prompt-orchestrator",
        description="Prompt Orchestrator CLI.",
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

    for command, help_text in (
        ("understand", "Return the validated execution plan."),
        ("plan", "Render the worker prompt plan without calling the worker."),
        ("run", "Run the complete prompt orchestration pipeline."),
    ):
        command_parser = subparsers.add_parser(command, help=help_text)
        _add_runtime_arguments(command_parser)
        command_parser.set_defaults(handler=_handler_for(command))

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
    except PromptOrchestratorError as exc:
        if getattr(args, "json", False):
            print(render_json(_error_payload(exc)))
        else:
            print(f"Error [{exc.code}]: {exc}", file=sys.stderr)
        return _exit_code_for(exc)
    except Exception:
        if getattr(args, "debug", False):
            traceback.print_exc()
        else:
            print(
                "Error [UNEXPECTED_ERROR]: Unexpected internal error.",
                file=sys.stderr,
            )
        return 1


def _add_runtime_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("prompt", nargs="?", help="Prompt text.")
    parser.add_argument("--stdin", action="store_true", help="Read prompt from stdin.")
    parser.add_argument("--context", help="Optional caller context.")
    parser.add_argument("--config", help="Path to a YAML configuration file.")
    parser.add_argument(
        "--output-mode",
        choices=[mode.value for mode in OutputMode],
        help="Optional output mode override.",
    )
    parser.add_argument("--json", action="store_true", help="Render structured JSON.")
    parser.add_argument("--trace", action="store_true", help="Include trace metadata.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show stack traces for unexpected internal errors.",
    )


CommandHandler = Callable[[argparse.Namespace], int]


def _handler_for(command: str) -> CommandHandler:
    if command == "understand":
        return _handle_understand
    if command == "plan":
        return _handle_plan
    return _handle_run


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


def _handle_understand(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    include_trace = _include_trace(args, config)
    client = create_pipeline_client(config)
    request = _prompt_request_from_args(args)
    result = run_understanding_stage(request, config=config, client=client)
    if args.json:
        payload = result.validated_plan.model_dump(mode="json")
        if include_trace:
            payload["trace"] = result.trace.model_dump(mode="json")
        print(render_json(payload))
    else:
        print(render_understand_text(result.validated_plan))
        if include_trace:
            print(_render_trace_text(result.trace))
    return 0


def _handle_plan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    include_trace = _include_trace(args, config)
    client = create_pipeline_client(config)
    runner = PipelineRunner(config=config, client=client)
    result = runner.plan(_prompt_request_from_args(args), include_trace=include_trace)
    if args.json:
        print(render_json(_plan_payload(result)))
    else:
        print(render_plan_text(result))
        if include_trace and result.trace is not None:
            print(_render_trace_text(result.trace))
    if result.final_response is None:
        return 0
    return _status_exit_code(result.final_response.status.value)


def _handle_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    include_trace = _include_trace(args, config)
    client = create_pipeline_client(config)
    runner = PipelineRunner(config=config, client=client)
    result = runner.run(_prompt_request_from_args(args), include_trace=include_trace)
    response = result.final_response
    if args.json:
        print(render_json(response))
    else:
        print(render_final_text(response))
        if include_trace and response.trace is not None:
            print(_render_trace_text(response.trace))
    return _status_exit_code(response.status.value)


def _prompt_request_from_args(args: argparse.Namespace) -> PromptRequest:
    if args.stdin:
        prompt = sys.stdin.read()
        if args.prompt:
            prompt = f"{args.prompt}\n{prompt}"
    else:
        if args.prompt is None:
            raise InputError("Prompt argument is required unless --stdin is used.")
        prompt = args.prompt
    if not prompt.strip():
        raise InputError("Prompt must not be empty.", code="INPUT_EMPTY")
    return PromptRequest(
        prompt=prompt,
        context=args.context,
        requested_output_mode=args.output_mode,
    )


def _include_trace(
    args: argparse.Namespace,
    config: PromptOrchestratorConfig,
) -> bool:
    return bool(args.trace or config.runtime.trace.enabled_by_default)


def _plan_payload(result: PipelinePlanResult) -> dict[str, object]:
    payload: dict[str, object] = {"status": "planned"}
    if result.prompt_plan is not None:
        payload["prompt_plan"] = result.prompt_plan.model_dump(mode="json")
    if result.validated_plan is not None:
        payload["validated_plan"] = result.validated_plan.model_dump(mode="json")
    if result.final_response is not None:
        payload["final_response"] = result.final_response.model_dump(mode="json")
        payload["status"] = result.final_response.status.value
    if result.trace is not None:
        payload["trace"] = result.trace.model_dump(mode="json")
    return payload


def _render_trace_text(trace: Trace) -> str:
    lines = ["", "Trace:"]
    for event in trace.events:
        lines.append(
            f"- {event.stage}.{event.event}: {event.status} "
            f"({event.duration_ms:.1f} ms)"
        )
    return "\n".join(lines)


def _error_payload(exc: PromptOrchestratorError) -> dict[str, object]:
    return {
        "status": "failed",
        "error": {
            "code": exc.code,
            "message": str(exc),
            "retryable": False,
        },
    }


def _exit_code_for(exc: PromptOrchestratorError) -> int:
    if isinstance(exc, ConfigurationError):
        return 2
    if isinstance(exc, InputError):
        return 3
    if isinstance(exc, ProviderError):
        return 4
    return 5


def _status_exit_code(status: str) -> int:
    return 1 if status == "failed" else 0
