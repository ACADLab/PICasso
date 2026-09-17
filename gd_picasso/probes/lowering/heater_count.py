import numpy as np, sympy as sp
from mzi_extract import wrap
from lower import lower, CASES
from merge_phases import merged_layers, rebuild_merged
from psd_gate import infer_guarded
TOL=1e-9
def nz(x): return int(abs(wrap(x))>TOL)

print(f"{'circuit':16s} {'N':>2} {'MZI':>4} | {'th':>3} {'unmerged ph':>12} {'tot':>4} | "
      f"{'merged ph':>10} {'tot':>4} | {'saved':>6} {'err':>9}")
print("-"*82)
for name,(nin,spec) in CASES.items():
    r=infer_guarded(spec,nin)
    U=np.array(sp.Matrix(r["U"]).evalf().tolist(),dtype=complex)
    cells,D,N=lower(U)
    n_th=sum(nz(c.theta) for c in cells)
    pre = sum(nz(c.phi)+nz(c.out_a)+nz(c.out_b) for c in cells) + sum(nz(p) for p in np.angle(np.diag(D)))
    layers,cores=merged_layers(cells,D,N)
    post=sum(nz(x) for L in layers for x in L)
    err=np.linalg.norm(rebuild_merged(layers,cores,N)-U)
    a,b = n_th+pre, n_th+post
    print(f"{name:16s} {N:>2} {len(cells):>4} | {n_th:>3} {pre:>12} {a:>4} | "
          f"{post:>10} {b:>4} | {100*(a-b)/a:>5.0f}% {err:9.1e}")
