"""Collapse adjacent diagonal phase layers.

Each cell factors as   Dout(a,b) . [B P(th) B] . Din(ph)
so the full product    C1 C2 ... Ck D
factors as             Dout1 Core1 (Din1 Dout2) Core2 (Din2 Dout3) ... Cork (Dink D)
Adjacent diagonals merge in the full N-dim space; a heater is needed only where
the accumulated phase is nonzero mod 2pi.
"""
import numpy as np, sympy as sp
from mzi_extract import B, wrap
from lower import lower, embed, CASES
from psd_gate import infer_guarded

TOL = 1e-9

def core(th):
    return B @ np.diag([1, np.exp(1j*th)]) @ B

def merged_layers(cells, D, N):
    """Return (phase_layers, cores) with phase_layers[m] a length-N phase vector."""
    layers = [np.zeros(N) for _ in range(len(cells)+1)]
    cores  = []
    for m, c in enumerate(cells):
        i, j = c.modes
        layers[m][i] += c.out_a          # Dout of this cell
        layers[m][j] += c.out_b
        cores.append((c.modes, c.theta))
        layers[m+1][j] += c.phi          # Din of this cell
    layers[-1] += np.angle(np.diag(D))   # residual diagonal folds into last layer
    return [np.array([wrap(x) for x in L]) for L in layers], cores

def rebuild_merged(layers, cores, N):
    M = np.eye(N, dtype=complex)
    for m, (modes, th) in enumerate(cores):
        M = M @ np.diag(np.exp(1j*layers[m]))
        M = M @ embed(core(th), *modes, N)
    M = M @ np.diag(np.exp(1j*layers[-1]))
    return M

print(f"{'circuit':16s} {'N':>2} {'MZIs':>5} {'naive':>6} {'merged':>7} {'saved':>6} {'||err||':>10}")
print("-"*60)
for name,(nin,spec) in CASES.items():
    r = infer_guarded(spec, nin)
    U = np.array(sp.Matrix(r["U"]).evalf().tolist(), dtype=complex)
    cells, D, N = lower(U)
    layers, cores = merged_layers(cells, D, N)
    err = np.linalg.norm(rebuild_merged(layers, cores, N) - U)
    naive  = 3*len(cells) + N
    merged = sum(int(abs(x) > TOL) for L in layers for x in L) + len(cores)  # +theta heaters
    print(f"{name:16s} {N:>2} {len(cells):>5} {naive:>6} {merged:>7} "
          f"{100*(naive-merged)/naive:>5.0f}% {err:10.2e}")
