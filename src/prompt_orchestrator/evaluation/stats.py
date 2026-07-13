"""Small, dependency-free statistics for interpreting evaluation results.

Comparing arms on a handful of cases is meaningless without uncertainty: "6/8 vs
5/8" could be noise. These helpers report a proportion with a Wilson confidence
interval and run paired significance tests (sign test on pairwise wins, McNemar
on paired pass/fail). Everything uses the Python standard library only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# z for a two-sided 95% interval; adequate for reporting without scipy.
_Z_95 = 1.959963984540054


@dataclass(frozen=True)
class Proportion:
    """A proportion with a Wilson score confidence interval."""

    successes: int
    total: int
    point: float
    low: float
    high: float


def wilson_interval(successes: int, total: int, z: float = _Z_95) -> Proportion:
    """Wilson score interval for a binomial proportion (stable at small n)."""
    if total <= 0:
        return Proportion(successes=0, total=0, point=0.0, low=0.0, high=0.0)
    if successes < 0 or successes > total:
        raise ValueError("successes must be within [0, total]")
    phat = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (phat + z2 / (2 * total)) / denom
    margin = (z * math.sqrt((phat * (1 - phat) + z2 / (4 * total)) / total)) / denom
    return Proportion(
        successes=successes,
        total=total,
        point=phat,
        low=max(0.0, center - margin),
        high=min(1.0, center + margin),
    )


def sign_test_p_value(wins: int, losses: int) -> float:
    """Two-sided exact sign test p-value for paired wins vs losses (ties dropped).

    Under the null (no difference), wins ~ Binomial(n, 0.5). Returns 1.0 when
    there are no decisive pairs.
    """
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    tail = sum(_binom_pmf(n, i, 0.5) for i in range(0, k + 1))
    return min(1.0, 2.0 * tail)


def mcnemar_p_value(treatment_only: int, control_only: int) -> float:
    """Two-sided exact McNemar p-value on paired pass/fail disagreements.

    ``treatment_only`` = cases the treatment passed but the control failed;
    ``control_only`` = the reverse. Concordant pairs carry no information.
    """
    return sign_test_p_value(treatment_only, control_only)


def _binom_pmf(n: int, k: int, p: float) -> float:
    return math.comb(n, k) * (p**k) * ((1 - p) ** (n - k))


def bootstrap_mean_interval(
    values: list[float],
    *,
    resamples: int = 2000,
    z: float = _Z_95,
) -> tuple[float, float, float]:
    """Return (mean, low, high) using a normal-approximation on the values.

    A deterministic approximation is used instead of random resampling so results
    are reproducible and no RNG is required; ``resamples`` is accepted for API
    stability. For n <= 1 the interval collapses to the point estimate.
    """
    n = len(values)
    if n == 0:
        return (0.0, 0.0, 0.0)
    mean = sum(values) / n
    if n == 1:
        return (mean, mean, mean)
    variance = sum((value - mean) ** 2 for value in values) / (n - 1)
    stderr = math.sqrt(variance / n)
    margin = z * stderr
    return (mean, mean - margin, mean + margin)


def sample_size_for_win_rate(
    detectable_delta: float,
    *,
    z: float = _Z_95,
) -> int:
    """Rough paired-comparison sample size to resolve a win-rate ``detectable_delta``
    away from 0.5 (worst-case variance at p=0.5). Guidance, not a power analysis.
    """
    if not 0.0 < detectable_delta <= 0.5:
        raise ValueError("detectable_delta must be in (0, 0.5]")
    n = (z * 0.5 / detectable_delta) ** 2
    return math.ceil(n)
