"""Score candidate MZI conventions against the 2x2 blocks Clements emits.

Physical MZI on Cornerstone: MMI1x2 -> [heater arm] -> MMI1x2, plus an input heater.
    MZI(th,ph) = B @ diag(e^{i th},1) @ B @ diag(e^{i ph},1)
B is the 50:50 coupler; its convention is the thing in dispute.
A trailing output diagonal is FREE because Clements pushes it into the next layer.
"""
import numpy as np
from scipy.optimize import minimize

COUPLERS = {
    "B_i   (1/r2)[[1,i],[i,1]]" : np.array([[1,1j],[1j,1]])/np.sqrt(2),
    "B_h   (1/r2)[[1,1],[1,-1]]": np.array([[1,1],[1,-1]])/np.sqrt(2),
    "B_mi  (1/r2)[[1,-i],[-i,1]]":np.array([[1,-1j],[-1j,1]])/np.sqrt(2),
}
ARMS = {"top": lambda t: np.diag([np.exp(1j*t), 1.0]),
        "bot": lambda t: np.diag([1.0, np.exp(1j*t)])}

def mzi(B, arm, th, ph):
    return B @ ARMS[arm](th) @ B @ ARMS[arm](ph)

def fit(T, B, arm, free_out_diag):
    """Best ||T - Dout@MZI(th,ph)|| over th,ph (and Dout if free)."""
    def cost(x):
        M = mzi(B, arm, x[0], x[1])
        if free_out_diag:
            # optimal diagonal phase per row, closed form
            d = np.array([np.vdot(M[k,:], T[k,:]) for k in range(2)])
            d = np.where(np.abs(d)>1e-14, d/np.abs(d), 1.0)
            M = np.diag(d.conj()).conj() @ M
            M = np.diag(d/np.abs(d)) @ mzi(B, arm, x[0], x[1])
        return np.linalg.norm(T - M)
    best = np.inf
    for s in range(12):
        rng = np.random.default_rng(s)
        r = minimize(cost, rng.uniform(0, 2*np.pi, 2), method="Nelder-Mead",
                     options={"xatol":1e-12,"fatol":1e-14,"maxiter":4000})
        best = min(best, r.fun)
    return best

def rand_su2(seed):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(2,2)) + 1j*rng.normal(size=(2,2))
    Q,R = np.linalg.qr(X); Q = Q @ np.diag(np.diag(R)/abs(np.diag(R)))
    return Q / np.sqrt(np.linalg.det(Q))          # force det=1, as Givens blocks are

targets = [rand_su2(s) for s in range(6)]
print(f"{'coupler':28s} {'arm':4s} {'free Dout':>10s} {'worst resid':>13s}")
print("-"*60)
rows=[]
for bn,B in COUPLERS.items():
    for arm in ARMS:
        for free in (False, True):
            w = max(fit(T,B,arm,free) for T in targets)
            rows.append((w,bn,arm,free))
            print(f"{bn:28s} {arm:4s} {str(free):>10s} {w:13.2e}")
print("-"*60)
rows.sort()
w,bn,arm,free = rows[0]
print(f"BEST: {bn}  arm={arm}  free_out_diag={free}  worst residual={w:.2e}")
