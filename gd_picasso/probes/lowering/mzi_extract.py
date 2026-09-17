"""Closed-form MZI parameter extraction.

Convention (fixed after the sweep in mzi_conventions.py):
    B = (1/sqrt2)[[1,1],[1,-1]]          50:50 MMI
    MZI(th,ph) = B @ diag(1,e^{i th}) @ B @ diag(1,e^{i ph})
               = e^{i th/2} [[ cos(th/2), -i sin(th/2) e^{i ph}],
                             [-i sin(th/2),   cos(th/2) e^{i ph}]]
    Realized block = diag(e^{ia}, e^{ib}) @ MZI(th,ph)      <-- output diag REQUIRED

Returns (th, ph, a, b). th = internal arm phase, ph = input phase,
(a,b) = per-mode output phases that must be physically present.
"""
import numpy as np

B = np.array([[1,1],[1,-1]], dtype=complex)/np.sqrt(2)

def mzi(th, ph):
    return B @ np.diag([1, np.exp(1j*th)]) @ B @ np.diag([1, np.exp(1j*ph)])

def realized(th, ph, a, b):
    return np.diag([np.exp(1j*a), np.exp(1j*b)]) @ mzi(th, ph)

def extract(T, tol=1e-12):
    c, s = abs(T[0,0]), abs(T[0,1])
    th = 2*np.arctan2(s, c)
    half = th/2
    if abs(np.sin(half)) < tol:            # bar state: T is diagonal
        ph = 0.0
        a  = np.angle(T[0,0]) - half
        b  = np.angle(T[1,1]) - half
    elif abs(np.cos(half)) < tol:          # cross state: T is antidiagonal
        ph  = 0.0
        a   = np.angle(T[0,1]) - half - np.angle(-1j*np.sin(half))
        b   = np.angle(T[1,0]) - half - np.angle(-1j*np.sin(half))
        ph  = 0.0
    else:
        ph = np.angle(T[0,1]) - np.angle(T[0,0]) - np.angle(-1j)
        a  = np.angle(T[0,0]) - half
        b  = np.angle(T[1,0]) - half - np.angle(-1j*np.sin(half))
    return th, ph, a, b

def wrap(x): return (x + np.pi) % (2*np.pi) - np.pi

if __name__ == "__main__":
    def rand_su2(seed):
        rng = np.random.default_rng(seed)
        X = rng.normal(size=(2,2)) + 1j*rng.normal(size=(2,2))
        Q,R = np.linalg.qr(X); Q = Q @ np.diag(np.diag(R)/abs(np.diag(R)))
        return Q/np.sqrt(np.linalg.det(Q))
    worst = 0.0
    for s in range(400):
        T = rand_su2(s)
        e = np.linalg.norm(T - realized(*extract(T)))
        worst = max(worst, e)
    print(f"random SU(2), n=400      worst ||T - realized|| = {worst:.3e}")
    for name, T in [("bar  I",   np.eye(2,dtype=complex)),
                    ("cross",    np.array([[0,1],[-1,0]],dtype=complex)),
                    ("hadamard", np.array([[1,1],[1,-1]],dtype=complex)/np.sqrt(2))]:
        th,ph,a,b = extract(T)
        print(f"{name:10s} th={wrap(th):+.4f} ph={wrap(ph):+.4f} "
              f"a={wrap(a):+.4f} b={wrap(b):+.4f}  err={np.linalg.norm(T-realized(th,ph,a,b)):.2e}")
