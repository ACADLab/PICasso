"""
Hard min-plus (tropical) curvy-routing kernel + soft logsumexp twin.

Primary detailed router for Paper B when this matches LiDAR within margin;
otherwise cut line fires → LiDAR wrap is primary (cite; no GPU-router novelty).

CPU torch/numpy implementation ships here; GPU is optional via CUDA tensors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

try:
    import torch

    _HAVE_TORCH = True
except Exception:  # pragma: no cover
    torch = None  # type: ignore
    _HAVE_TORCH = False


@dataclass
class MinPlusResult:
    cost: np.ndarray  # [H, W] or [N, H, W]
    path_cost: float
    backend: str
    matched_lidar: Optional[bool] = None
    detail: str = ""


def min_plus_relax(
    C: np.ndarray,
    A: np.ndarray,
    *,
    iterations: int = 8,
) -> np.ndarray:
    """Hard min-plus fixed point: C ← min(C, min_plus(C, A)).

    ``C`` is cost-to-come on a grid (H,W). ``A`` is a sparse stencil of
    shape (K, 3) rows ``(di, dj, w)`` relative offsets + transition weight.
    """
    H, W = C.shape
    out = C.copy()
    for _ in range(iterations):
        nxt = out.copy()
        for di, dj, w in A:
            di, dj = int(di), int(dj)
            # Shifted slice
            src = out
            # Destination region
            i0 = max(0, di)
            j0 = max(0, dj)
            i1 = min(H, H + di) if di < 0 else min(H, H)
            j1 = min(W, W + dj) if dj < 0 else min(W, W)
            si0 = i0 - di
            sj0 = j0 - dj
            si1 = si0 + (i1 - i0)
            sj1 = sj0 + (j1 - j0)
            if i1 <= i0 or j1 <= j0:
                continue
            cand = src[si0:si1, sj0:sj1] + float(w)
            nxt[i0:i1, j0:j1] = np.minimum(nxt[i0:i1, j0:j1], cand)
        out = nxt
    return out


def soft_min_plus_relax(
    C: np.ndarray,
    A: np.ndarray,
    *,
    tau: float = 1.0,
    iterations: int = 8,
) -> np.ndarray:
    """Soft twin: logsumexp relaxation; as ``τ→0`` approaches hard min-plus."""
    tau = max(float(tau), 1e-8)
    H, W = C.shape
    out = C.copy()
    for _ in range(iterations):
        # Start with current cost as a candidate (−C/τ in log-space).
        logs = [-out / tau]
        for di, dj, w in A:
            di, dj = int(di), int(dj)
            cand = np.full((H, W), -np.inf, dtype=np.float64)
            i0 = max(0, di)
            j0 = max(0, dj)
            i1 = min(H, H + di) if di < 0 else H
            j1 = min(W, W + dj) if dj < 0 else W
            si0 = i0 - di
            sj0 = j0 - dj
            si1 = si0 + (i1 - i0)
            sj1 = sj0 + (j1 - j0)
            if i1 <= i0 or j1 <= j0:
                continue
            finite = np.isfinite(out[si0:si1, sj0:sj1])
            block = np.full((i1 - i0, j1 - j0), -np.inf)
            block[finite] = -(out[si0:si1, sj0:sj1][finite] + float(w)) / tau
            cand[i0:i1, j0:j1] = block
            logs.append(cand)
        stacked = np.stack(logs, axis=0)
        # Mask −inf for stability
        mx = np.max(stacked, axis=0)
        mx = np.where(np.isfinite(mx), mx, 0.0)
        exps = np.exp(stacked - mx)
        exps[~np.isfinite(stacked)] = 0.0
        out = -tau * (mx + np.log(np.maximum(exps.sum(axis=0), 1e-300)))
        # Preserve unreachable cells as +inf
        unreachable = ~np.isfinite(mx) | (exps.sum(axis=0) == 0)
        # Recompute reachability from original finite seed propagation:
        out = np.where(np.isfinite(C) | np.isfinite(out), out, np.inf)
        # Cells that stayed −inf in all logs → inf
        all_neg_inf = np.all(~np.isfinite(stacked), axis=0)
        out = np.where(all_neg_inf, np.inf, out)
    return out


def soft_grad_check(
    C0: np.ndarray,
    A: np.ndarray,
    *,
    tau: float = 0.5,
    eps: float = 1e-4,
) -> float:
    """Max |∂F̂/∂C_ij − FD| over a few samples (soft twin sanity)."""
    if not _HAVE_TORCH:
        # Numpy FD vs FD self → 0; report nan to signal no torch
        return float("nan")
    assert torch is not None
    C = torch.tensor(C0, dtype=torch.float64, requires_grad=True)
    A_t = [(int(di), int(dj), float(w)) for di, dj, w in A]

    def soft_once(C_t: "torch.Tensor") -> "torch.Tensor":
        out = C_t
        for _ in range(4):
            m = -out / tau
            for di, dj, w in A_t:
                H, W = out.shape
                i0 = max(0, di)
                j0 = max(0, dj)
                i1 = H if di >= 0 else H
                j1 = W if dj >= 0 else W
                if di < 0:
                    i0 = 0
                    i1 = H + di
                if dj < 0:
                    j0 = 0
                    j1 = W + dj
                si0 = i0 - di
                sj0 = j0 - dj
                si1 = si0 + (i1 - i0)
                sj1 = sj0 + (j1 - j0)
                if i1 <= i0 or j1 <= j0:
                    continue
                cand = -(out[si0:si1, sj0:sj1] + w) / tau
                region = m[i0:i1, j0:j1]
                mx = torch.maximum(region, cand)
                m = m.clone()
                m[i0:i1, j0:j1] = mx + torch.log(
                    torch.exp(region - mx) + torch.exp(cand - mx)
                )
            out = -tau * m
        return out.sum()

    f = soft_once(C)
    f.backward()
    g = C.grad.detach().numpy()
    # One-sided FD at a few cells
    C_np = C0.copy()
    errs = []
    for i, j in [(1, 1), (C0.shape[0] // 2, C0.shape[1] // 2)]:
        Cp = C_np.copy()
        Cp[i, j] += eps
        # reuse numpy soft
        fp = soft_min_plus_relax(Cp, A, tau=tau, iterations=4).sum()
        fm = soft_min_plus_relax(C_np, A, tau=tau, iterations=4).sum()
        fd = (fp - fm) / eps
        errs.append(abs(float(g[i, j]) - float(fd)))
    return float(max(errs)) if errs else float("nan")


def route_point_to_point(
    H: int,
    W: int,
    src: Tuple[int, int],
    dst: Tuple[int, int],
    *,
    bend_cost: float = 0.5,
    iterations: int = 16,
) -> MinPlusResult:
    """Hard min-plus on a 4-neighbor grid (orientation-free smoke kernel)."""
    C = np.full((H, W), np.inf, dtype=np.float64)
    C[src] = 0.0
    # 4-neighbor stencil + mild bend (uniform)
    A = np.array(
        [
            [-1, 0, 1.0],
            [1, 0, 1.0],
            [0, -1, 1.0],
            [0, 1, 1.0],
            [-1, -1, 1.0 + bend_cost],
            [-1, 1, 1.0 + bend_cost],
            [1, -1, 1.0 + bend_cost],
            [1, 1, 1.0 + bend_cost],
        ],
        dtype=np.float64,
    )
    Cf = min_plus_relax(C, A, iterations=iterations)
    return MinPlusResult(
        cost=Cf,
        path_cost=float(Cf[dst]),
        backend="numpy",
        detail="hard min-plus 8-neighbor smoke; GPU optional later",
    )


def soft_approaches_hard(
    H: int = 16,
    W: int = 16,
    *,
    taus: Tuple[float, ...] = (2.0, 0.5, 0.1, 0.02),
) -> dict:
    """Show soft → hard as τ→0 (max |C_soft − C_hard| decreasing trend)."""
    src, dst = (1, 1), (H - 2, W - 2)
    hard = route_point_to_point(H, W, src, dst, iterations=20)
    A = np.array(
        [
            [-1, 0, 1.0],
            [1, 0, 1.0],
            [0, -1, 1.0],
            [0, 1, 1.0],
        ],
        dtype=np.float64,
    )
    C0 = np.full((H, W), np.inf)
    C0[src] = 0.0
    # Seed hard with same stencil for fair compare
    hard_c = min_plus_relax(C0.copy(), A, iterations=20)
    gaps = []
    for tau in taus:
        soft = soft_min_plus_relax(C0.copy(), A, tau=tau, iterations=20)
        mask = np.isfinite(hard_c) & np.isfinite(soft)
        if not mask.any():
            gaps.append(float("inf"))
        else:
            gaps.append(float(np.max(np.abs(hard_c[mask] - soft[mask]))))
    return {"taus": list(taus), "max_abs_gap": gaps, "hard_path_cost": hard.path_cost}


# Cut-line bookkeeping for Paper B claims
ROUTER_CUT_LINE = (
    "If hard GPU min-plus does not match LiDAR IL_max/wirelength within margin "
    "by end of calendar day 3 of dedicated router work (or two agent↔machine "
    "debug cycles after the 8–24h budget), Paper B ships LiDAR wrap as primary "
    "detailed router; hard/soft min-plus demoted to appendix."
)
