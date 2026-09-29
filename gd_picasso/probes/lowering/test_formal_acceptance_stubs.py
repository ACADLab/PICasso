"""Formal acceptance stubs — PSD reject + 1e-13 slice wait on λλ/Env.

Run:  python -m gd_picasso.probes.lowering.test_formal_acceptance_stubs
"""

from __future__ import annotations

import sys

import numpy as np


def test_numpy_psd_rejects_gain() -> None:
    from gd_picasso.probes.lowering.psd_numpy import (
        assert_transfer_psd_feasible,
        is_transfer_psd_feasible,
    )

    # Passive gain: |t|=2 on a 1x1
    ok, evs = is_transfer_psd_feasible([[2.0 + 0j]])
    assert not ok
    assert evs[0] < 0

    raised = False
    try:
        assert_transfer_psd_feasible([[2.0 + 0j]])
    except ValueError as e:
        raised = True
        assert "unrealizable" in str(e)
    assert raised


def test_numpy_psd_accepts_unitary_2x2() -> None:
    from gd_picasso.probes.lowering.psd_numpy import is_transfer_psd_feasible

    # Hadamard / balanced splitter (unitary)
    s = 1.0 / np.sqrt(2.0)
    H = np.array([[s, s], [s, -s]], dtype=np.complex128)
    ok, evs = is_transfer_psd_feasible(H)
    assert ok
    assert np.all(evs >= -1e-10)


def test_numpy_psd_accepts_subunitary_tap() -> None:
    from gd_picasso.probes.lowering.psd_numpy import is_transfer_psd_feasible

    # 90:10 intensity tap on one output row — sub-unitary, PSD-feasible
    A = np.array([[np.sqrt(0.9)]], dtype=np.complex128)
    ok, _ = is_transfer_psd_feasible(A)
    assert ok


def test_a1_stub_shape_and_partition_guard() -> None:
    from gd_picasso.pcg.types import LoweredMZIAnnotation, SpecAnnotation
    from gd_picasso.probes.lowering.to_a1 import (
        A1_CONTRACT_VERSION,
        LoweringA1NotReady,
        cells_to_a1_mutations,
    )

    assert A1_CONTRACT_VERSION == 1
    ann = [
        LoweredMZIAnnotation(
            modes=(0, 1),
            theta_rad=0.1,
            phi_rad=0.2,
            out_a_rad=0.0,
            out_b_rad=0.0,
        )
    ]
    muts, out = cells_to_a1_mutations(ann)
    assert muts == []
    assert len(out) == 1

    bad = SpecAnnotation(n_inputs=1, partition="non_expressible", task_id=23)
    raised = False
    try:
        cells_to_a1_mutations(ann, spec=bad)
    except ValueError:
        raised = True
    assert raised

    raised2 = False
    try:
        cells_to_a1_mutations(ann, expand_instances=True)
    except LoweringA1NotReady:
        raised2 = True
    assert raised2


def test_psd_gate_reject_waits_on_ll() -> None:
    """Acceptance: PSD reject via λλ parse — SKIP until Env vendors patch."""
    try:
        import unitary_inference  # noqa: F401
        from psd_gate import infer_guarded
    except ImportError:
        print("SKIP test_psd_gate_reject_waits_on_ll: unitary_inference not installed")
        return

    raised = False
    try:
        infer_guarded(["output(1) = 2*input(1)"], 1)
    except ValueError as e:
        raised = True
        assert "unrealizable" in str(e).lower() or "gain" in str(e).lower()
    assert raised, "patched λλ PSD gate must reject gain specs"


def test_vertical_slice_1e13_waits_on_ll() -> None:
    """Acceptance: ‖T−αU‖ ~ 1e-13 — SKIP until λλ + CS re-measure."""
    try:
        import unitary_inference  # noqa: F401
        from lower import CASES, lower, rebuild
        from psd_gate import infer_guarded
        import sympy as sp
    except ImportError:
        print("SKIP test_vertical_slice_1e13_waits_on_ll: λλ / lower deps missing")
        return

    name = "MZI 2x2"
    nin, spec = CASES[name]
    r = infer_guarded(spec, nin)
    U = np.array(sp.Matrix(r["U"]).evalf().tolist(), dtype=complex)
    cells, D, N = lower(U)
    err = np.linalg.norm(rebuild(cells, D, N) - U)
    assert err < 1e-12, f"{name} rebuild residual {err}"


def main() -> int:
    tests = [
        test_numpy_psd_rejects_gain,
        test_numpy_psd_accepts_unitary_2x2,
        test_numpy_psd_accepts_subunitary_tap,
        test_a1_stub_shape_and_partition_guard,
        test_psd_gate_reject_waits_on_ll,
        test_vertical_slice_1e13_waits_on_ll,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
