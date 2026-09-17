"""spec -> U -> Clements -> per-MZI (th,ph,a,b) -> netlist-ready cell list.
Verifies the whole lowering numerically against the spec matrix, no SAX needed.
"""
import numpy as np, sympy as sp
from dataclasses import dataclass
from typing import List
from psd_gate import infer_guarded
from unitary_inference import clements_decomposition
from mzi_extract import extract, realized, wrap

@dataclass
class MZICell:
    modes: tuple          # (i,j) waveguide pair
    theta: float          # internal arm phase  -> heater on one MZI arm
    phi:   float          # input phase         -> heater before the MZI
    out_a: float          # output phase mode i -> heater after
    out_b: float          # output phase mode j -> heater after

def embed(M2, i, j, N):
    M = np.eye(N, dtype=complex); M[np.ix_([i,j],[i,j])] = M2; return M

def lower(U: np.ndarray):
    N = U.shape[0]
    ops, phases = clements_decomposition(sp.Matrix(U))
    D = np.diag([complex(sp.N(p)) for p in phases])
    cells: List[MZICell] = []
    for i, j, G in ops:
        Gh = np.array(sp.Matrix(G).evalf().tolist(), dtype=complex).conj().T
        th, ph, a, b = extract(Gh)
        cells.append(MZICell((i,j), wrap(th), wrap(ph), wrap(a), wrap(b)))
    return cells, D, N

def rebuild(cells, D, N):
    M = np.eye(N, dtype=complex)
    for c in cells:
        M = M @ embed(realized(c.theta, c.phi, c.out_a, c.out_b), *c.modes, N)
    return M @ D

CASES = {
 "MZI 2x2":        (2, ["output(1) = (input(1) + input(2))/sqrt(2)",
                        "output(2) = (input(1) - input(2))/sqrt(2)"]),
 "2x2 cross":      (2, ["output(1) = input(2)", "output(2) = input(1)"]),
 "4x4 crossbar":   (4, ["output(1) = input(3)","output(2) = input(4)",
                        "output(3) = input(1)","output(4) = input(2)"]),
 "Clements 4x4 H": (4, ["output(1) = (input(1)+input(2)+input(3)+input(4))/2",
                        "output(2) = (input(1)-input(2)+input(3)-input(4))/2",
                        "output(3) = (input(1)+input(2)-input(3)-input(4))/2",
                        "output(4) = (input(1)-input(2)-input(3)+input(4))/2"]),
 "4-pt DFT":       (4, ["output(1) = (input(1)+input(2)+input(3)+input(4))/2",
                        "output(2) = (input(1)+I*input(2)-input(3)-I*input(4))/2",
                        "output(3) = (input(1)-input(2)+input(3)-input(4))/2",
                        "output(4) = (input(1)-I*input(2)-input(3)+I*input(4))/2"]),
 "90deg hybrid":   (4, ["output(1) = (input(1) + input(2))/2",
                        "output(2) = (input(1) - input(2))/2",
                        "output(3) = (input(1) + I*input(2))/2",
                        "output(4) = (input(1) - I*input(2))/2"]),
}

print(f"{'circuit':16s} {'N':>2} {'anc':>4} {'MZIs':>5} {'heaters':>8} {'||rebuilt-U||':>14}")
print("-"*58)
for name,(nin,spec) in CASES.items():
    r = infer_guarded(spec, nin)
    U = np.array(sp.Matrix(r["U"]).evalf().tolist(), dtype=complex)
    cells, D, N = lower(U)
    err = np.linalg.norm(rebuild(cells,D,N) - U)
    heaters = 3*len(cells) + N          # th + ph + 2 out per MZI (shared), + residual D
    print(f"{name:16s} {N:>2} {r['ancillas']:>4} {len(cells):>5} {heaters:>8} {err:14.2e}")
