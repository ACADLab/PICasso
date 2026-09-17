"""Step 0: pin down how (ops, phases) from clements_decomposition rebuild U."""
import numpy as np, sympy as sp
from unitary_inference import clements_decomposition

def embed(G, i, j, N):
    M = np.eye(N, dtype=complex)
    M[np.ix_([i,j],[i,j])] = G
    return M

def rand_unitary(N, seed):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(N,N)) + 1j*rng.normal(size=(N,N))
    Q,R = np.linalg.qr(X)
    return Q @ np.diag(np.diag(R)/abs(np.diag(R)))

def candidates(ops, phases, N):
    D = np.diag(np.array([complex(sp.N(p)) for p in phases]))
    Gs = [(i,j,np.array(sp.Matrix(G).evalf().tolist(), dtype=complex)) for i,j,G in ops]
    out = {}
    # forward product  G_k...G_1
    P = np.eye(N, dtype=complex)
    for i,j,G in Gs: P = embed(G,i,j,N) @ P
    out["Gk..G1"] = P
    # reverse-dagger:  G_1^H ... G_k^H  D
    Q = np.eye(N, dtype=complex)
    for i,j,G in Gs: Q = Q @ embed(G.conj().T,i,j,N)
    out["G1H..GkH @ D"] = Q @ D
    out["D @ G1H..GkH"] = D @ Q
    return out

print(f"{'N':>2} {'seed':>4}  " + "  ".join(f"{k:>16s}" for k in ["Gk..G1","G1H..GkH @ D","D @ G1H..GkH"]))
for N in (2,3,4):
    for seed in (0,1):
        U = rand_unitary(N, seed)
        ops, ph = clements_decomposition(sp.Matrix(U))
        c = candidates(ops, ph, N)
        errs = {k: np.linalg.norm(v-U) for k,v in c.items()}
        print(f"{N:>2} {seed:>4}  " + "  ".join(f"{errs[k]:16.2e}" for k in ["Gk..G1","G1H..GkH @ D","D @ G1H..GkH"]))
