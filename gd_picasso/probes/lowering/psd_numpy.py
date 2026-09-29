"""Pure-numpy PSD feasibility check (Algorithm-1 guard, matrix form).

Does **not** parse λλ specs — that needs patched ``unitary_inference``.
Given a complex transfer block ``A`` (rows = outputs, cols = inputs),
``I - A A^H`` must be positive semidefinite for the spec to be
physically realizable without gain.

Lane Formal ships this so PSD docs / unit tests run without λλ.
Full ``infer_guarded(spec_lines, n)`` remains in ``psd_gate.py`` and
waits on Lane λλ/Env.
"""

from __future__ import annotations

from typing import Sequence, Tuple, Union

import numpy as np

ArrayLike = Union[np.ndarray, Sequence[Sequence[complex]]]


def is_transfer_psd_feasible(
    A: ArrayLike,
    *,
    tol: float = 1e-10,
) -> Tuple[bool, np.ndarray]:
    """Return ``(ok, eigenvalues)`` of Hermitian ``I - A @ A.conj().T``.

    ``ok`` is False iff any eigenvalue is meaningfully negative (gain).
    """
    M = np.asarray(A, dtype=np.complex128)
    if M.ndim != 2:
        raise ValueError(f"A must be 2-D, got shape {M.shape}")
    m = M.shape[0]
    S = np.eye(m, dtype=np.complex128) - M @ M.conj().T
    # Numerical Hermitianize
    S = 0.5 * (S + S.conj().T)
    evs = np.linalg.eigvalsh(S)
    ok = bool(np.all(evs >= -tol))
    return ok, evs


def assert_transfer_psd_feasible(A: ArrayLike, *, tol: float = 1e-10) -> np.ndarray:
    """Raise ``ValueError`` with the same spirit as ``psd_gate.infer_guarded``."""
    ok, evs = is_transfer_psd_feasible(A, tol=tol)
    if not ok:
        bad = evs[evs < -tol]
        raise ValueError(
            f"unrealizable: spec demands gain (neg eigenvalue(s) {bad.tolist()} "
            f"of I-AA^H)"
        )
    return evs
