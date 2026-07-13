"""Evaluation arms: the treatment and the controls it is measured against.

An arm is a named way of answering a prompt. The treatment is full orchestration
(`run`). The controls are the alternatives orchestration must beat to justify its
cost — especially the *equal-compute* controls (best-of-N, self-refine), which
spend a comparable token budget a different way. Ablations remove a single stage
to attribute any lift to that stage.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from prompt_orchestrator.domain import FinalResponse, PromptRequest
from prompt_orchestrator.exceptions import InputError
from prompt_orchestrator.pipeline import PipelineRunner

TREATMENT_NAME = "orchestrated"
CONTROL_KINDS = ("single_call", "best_of_n", "self_refine")


@dataclass(frozen=True)
class Arm:
    """One named strategy for answering a prompt, plus how to run it."""

    name: str
    kind: str
    run: Callable[[PromptRequest], FinalResponse]
    is_treatment: bool = False


@dataclass(frozen=True)
class ArmSpec:
    """Which control arms and ablations to compare the treatment against."""

    controls: tuple[str, ...] = ("single_call",)
    best_of_n: int = 3
    ablations: bool = False

    def validated(self) -> ArmSpec:
        for kind in self.controls:
            if kind not in CONTROL_KINDS:
                raise InputError(
                    f"Unknown eval arm '{kind}'. "
                    f"Choose from: {', '.join(CONTROL_KINDS)}.",
                    code="EVAL_ARM_UNKNOWN",
                )
        if self.best_of_n < 1:
            raise InputError(
                "best-of-n requires a value >= 1.",
                code="EVAL_BEST_OF_N_N",
            )
        return self


def build_arms(runner: PipelineRunner, spec: ArmSpec) -> list[Arm]:
    """Build the ordered arm list: treatment first, then controls and ablations."""
    spec = spec.validated()
    arms: list[Arm] = [
        Arm(
            name=TREATMENT_NAME,
            kind="orchestrated",
            run=lambda request: runner.run(request).final_response,
            is_treatment=True,
        )
    ]
    for kind in spec.controls:
        arms.append(_control_arm(runner, kind, spec.best_of_n))
    if spec.ablations:
        arms.extend(_ablation_arms(runner))
    _reject_duplicate_names(arms)
    return arms


def _control_arm(runner: PipelineRunner, kind: str, best_of_n: int) -> Arm:
    if kind == "single_call":
        return Arm(name="single_call", kind=kind, run=runner.run_baseline)
    if kind == "best_of_n":
        return Arm(
            name=f"best_of_{best_of_n}",
            kind=kind,
            run=_best_of_n_runner(runner, best_of_n),
        )
    if kind == "self_refine":
        return Arm(name="self_refine", kind=kind, run=runner.run_self_refine)
    raise InputError(f"Unknown eval arm '{kind}'.", code="EVAL_ARM_UNKNOWN")


def _best_of_n_runner(
    runner: PipelineRunner, n: int
) -> Callable[[PromptRequest], FinalResponse]:
    def run(request: PromptRequest) -> FinalResponse:
        return runner.run_best_of_n(request, n=n)

    return run


def _ablation_arms(runner: PipelineRunner) -> list[Arm]:
    no_critic = runner.with_overrides(enable_critic=False)
    no_revision = runner.with_overrides(enable_revision=False)
    return [
        Arm(
            name="ablation_no_critic",
            kind="ablation",
            run=lambda request: no_critic.run(request).final_response,
        ),
        Arm(
            name="ablation_no_revision",
            kind="ablation",
            run=lambda request: no_revision.run(request).final_response,
        ),
    ]


def _reject_duplicate_names(arms: list[Arm]) -> None:
    seen: set[str] = set()
    for arm in arms:
        if arm.name in seen:
            raise InputError(
                f"Duplicate eval arm name '{arm.name}'.",
                code="EVAL_ARM_DUPLICATE",
            )
        seen.add(arm.name)
