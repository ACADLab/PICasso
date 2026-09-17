"""The feasibility guard from Algorithm 1 lines 4-6, which the code omits."""
import sympy as sp
from unitary_inference import parse_spec_sympy_eval, infer_unitary_from_spec

def feasible(spec_lines, n_inputs):
    _, R = parse_spec_sympy_eval(spec_lines, n_inputs)
    S = sp.simplify(sp.eye(R.shape[0]) - R*R.H)
    evs = [sp.simplify(e) for e in S.eigenvals().keys()]
    bad = [e for e in evs if sp.re(sp.nsimplify(e)).is_negative]
    return (len(bad)==0), evs, bad

def infer_guarded(spec_lines, n_inputs):
    ok, evs, bad = feasible(spec_lines, n_inputs)
    if not ok:
        raise ValueError(f"unrealizable: spec demands gain (neg eigenvalue(s) {bad} of I-AA^H)")
    return infer_unitary_from_spec(spec_lines, n_inputs)
