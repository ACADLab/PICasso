"""Wilson CI unit goldens for N1."""

from __future__ import annotations

import math

from gd_picasso.pcg.n1_stats import (
    format_ci,
    intervals_overlap,
    no_win_claim,
    wilson_ci,
)


def test_wilson_perfect() -> None:
    ci = wilson_ci(10, 10)
    assert ci.p_hat == 1.0
    assert ci.low < 1.0
    assert ci.high == 1.0


def test_wilson_zero() -> None:
    ci = wilson_ci(0, 10)
    assert ci.p_hat == 0.0
    assert ci.low == 0.0
    assert ci.high > 0.0


def test_wilson_known_values() -> None:
    # Spot-check against known Wilson formula for k=5, n=10, z=1.96
    ci = wilson_ci(5, 10)
    assert abs(ci.p_hat - 0.5) < 1e-12
    # Approximate published bounds ~ [0.236, 0.764]
    assert 0.22 < ci.low < 0.25
    assert 0.75 < ci.high < 0.78


def test_empty_n() -> None:
    ci = wilson_ci(0, 0)
    assert math.isnan(ci.p_hat)


def test_overlap_and_no_win() -> None:
    a = wilson_ci(5, 10)
    b = wilson_ci(6, 10)
    assert intervals_overlap(a, b)
    assert no_win_claim([a, b])
    # Non-overlap: 10/10 vs 0/10
    c = wilson_ci(10, 10)
    d = wilson_ci(0, 10)
    assert not intervals_overlap(c, d)
    assert not no_win_claim([c, d])


def test_format_ci() -> None:
    s = format_ci(wilson_ci(3, 5))
    assert "3/5" in s
    assert "Wilson95%" in s
