"""PSD gate must reject gain-infeasible specs / transfer blocks (Algorithm 1).

Matrix-form coverage uses ``psd_numpy`` (no λλ). Spec-line coverage via
``psd_gate.infer_guarded`` runs only when ``unitary_inference`` is on
``PYTHONPATH`` (patched vendor — Lane λλ/Env).
"""

from __future__ import annotations

import numpy as np
import pytest

from gd_picasso.probes.lowering.psd_numpy import (
    assert_transfer_psd_feasible,
    is_transfer_psd_feasible,
)


def test_psd_numpy_rejects_gain_block():
    """A = 2·I demands power gain ⇒ I−AAᴴ has negative eigenvalues."""
    A = 2.0 * np.eye(2, dtype=complex)
    ok, evs = is_transfer_psd_feasible(A)
    assert ok is False
    assert np.any(evs < -1e-10)
    with pytest.raises(ValueError, match="unrealizable|gain"):
        assert_transfer_psd_feasible(A)


def test_psd_numpy_accepts_unitary_hadamard():
    H = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
    ok, evs = is_transfer_psd_feasible(H)
    assert ok is True
    assert np.all(evs >= -1e-10)


def test_psd_gate_rejects_infeasible_spec_when_ll_present():
    """Spec-line path: needs patched λλ ``unitary_inference``."""
    pytest.importorskip("unitary_inference")
    # Ensure probe flat-imports resolve (psd_gate lives beside unitary stubs).
    import gd_picasso.probes.lowering  # noqa: F401 — path bootstrap
    from psd_gate import infer_guarded

    # Amplifying 1→1 map: output = 2 * input ⇒ gain (classic Algorithm-1 reject).
    bad_spec = ["output(1) = 2*input(1)", "output(2) = 2*input(2)"]
    with pytest.raises(ValueError, match="unrealizable|gain"):
        infer_guarded(bad_spec, 2)
