"""N1 campaign statistics — pure-Python 95% Wilson score confidence intervals.

PROTOCOL_FREEZE.md: report Wilson 95% intervals; overlapping → no win claim.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple


# z for two-sided 95% normal approximation
_Z95 = 1.959963984540054


@dataclass(frozen=True)
class WilsonCI:
    n: int
    k: int
    p_hat: float
    low: float
    high: float

    @property
    def as_tuple(self) -> Tuple[float, float]:
        return (self.low, self.high)


def wilson_ci(k: int, n: int, *, z: float = _Z95) -> WilsonCI:
    """Wilson score interval for binomial proportion k/n at the given z.

    Returns a degenerate [0,0] or [1,1] style interval when n == 0
    (p_hat = nan, low=high=0.0) so callers can skip empty cells.
    """
    if n < 0 or k < 0 or k > n:
        raise ValueError(f"need 0 <= k <= n, got k={k}, n={n}")
    if n == 0:
        return WilsonCI(n=0, k=0, p_hat=float("nan"), low=0.0, high=0.0)

    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = p + z2 / (2.0 * n)
    margin = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    low = (centre - margin) / denom
    high = (centre + margin) / denom
    # Numerical clamp (float noise near 0/1)
    low = max(0.0, min(1.0, low))
    high = max(0.0, min(1.0, high))
    if k == 0:
        low = 0.0
    if k == n:
        high = 1.0
    return WilsonCI(n=n, k=k, p_hat=p, low=low, high=high)


def intervals_overlap(a: WilsonCI, b: WilsonCI) -> bool:
    """True if the closed intervals overlap (including touching endpoints)."""
    if a.n == 0 or b.n == 0:
        return True
    return not (a.high < b.low or b.high < a.low)


def no_win_claim(arm_cis: Sequence[WilsonCI]) -> bool:
    """PROTOCOL: overlapping Wilson 95% CIs → no win claim across arms."""
    usable = [c for c in arm_cis if c.n > 0]
    if len(usable) < 2:
        return True
    for i in range(len(usable)):
        for j in range(i + 1, len(usable)):
            if intervals_overlap(usable[i], usable[j]):
                return True
    return False


def summarize_arm_passes(
    passes: Iterable[bool],
) -> WilsonCI:
    seq = list(passes)
    n = len(seq)
    k = sum(1 for p in seq if p)
    return wilson_ci(k, n)


def format_ci(ci: WilsonCI, *, digits: int = 3) -> str:
    if ci.n == 0:
        return "n=0"
    return (
        f"{ci.k}/{ci.n}={ci.p_hat:.{digits}f} "
        f"Wilson95%[{ci.low:.{digits}f}, {ci.high:.{digits}f}]"
    )
