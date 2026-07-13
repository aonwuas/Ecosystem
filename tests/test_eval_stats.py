"""Tests for the dependency-free evaluation statistics helpers."""

from __future__ import annotations

import pytest

from prompt_orchestrator.evaluation.stats import (
    bootstrap_mean_interval,
    mcnemar_p_value,
    sample_size_for_win_rate,
    sign_test_p_value,
    wilson_interval,
)


def test_wilson_interval_known_value() -> None:
    result = wilson_interval(8, 10)
    assert result.point == pytest.approx(0.8)
    # Known Wilson 95% interval for 8/10 is approximately [0.490, 0.943].
    assert result.low == pytest.approx(0.490, abs=0.01)
    assert result.high == pytest.approx(0.943, abs=0.01)


def test_wilson_interval_empty_and_bounds() -> None:
    empty = wilson_interval(0, 0)
    assert empty.point == 0.0 and empty.low == 0.0 and empty.high == 0.0
    full = wilson_interval(5, 5)
    assert full.high == 1.0
    with pytest.raises(ValueError):
        wilson_interval(6, 5)


def test_sign_test_symmetric_and_decisive() -> None:
    assert sign_test_p_value(5, 5) == pytest.approx(1.0)
    assert sign_test_p_value(0, 0) == 1.0
    # 8 wins vs 2 losses over 10 decisive pairs: 2 * P(X <= 2), X ~ Bin(10, 0.5).
    assert sign_test_p_value(8, 2) == pytest.approx(0.109375)
    # A clean sweep is significant.
    assert sign_test_p_value(10, 0) < 0.01


def test_mcnemar_matches_sign_test() -> None:
    # McNemar on discordant pairs is an exact sign test.
    assert mcnemar_p_value(6, 0) == pytest.approx(0.03125)
    assert mcnemar_p_value(3, 3) == pytest.approx(1.0)


def test_bootstrap_mean_interval() -> None:
    mean, low, high = bootstrap_mean_interval([1.0, 1.0, 1.0])
    assert mean == pytest.approx(1.0)
    assert low == pytest.approx(1.0) and high == pytest.approx(1.0)
    mean2, low2, high2 = bootstrap_mean_interval([0.0, 1.0])
    assert mean2 == pytest.approx(0.5)
    assert low2 < 0.5 < high2


def test_sample_size_for_win_rate() -> None:
    # (1.96 * 0.5 / 0.1)^2 rounds up to 97.
    assert sample_size_for_win_rate(0.1) == 97
    assert sample_size_for_win_rate(0.25) < sample_size_for_win_rate(0.1)
    with pytest.raises(ValueError):
        sample_size_for_win_rate(0.0)
