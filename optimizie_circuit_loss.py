# optimize_circuit_loss.py
# Goal: Given a circuit built from S-matrix blocks and bidirectional connections,
#   1) compute global transfer T_net from chosen input ports to chosen output ports,
#   2) get the SVD upper bound (sigma_max^2) and its optimal multi-port drive vector,
#   3) tune internal phases to *maximize* that SVD bound,
#   4) report before/after metrics and the actual achieved delivery using the SVD-optimal drive.

from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Sequence


# ---------- Utilities ----------
def db_to_amp(loss_db: float) -> float:
    return 10 ** (-loss_db / 20.0)

def db10_from_power(p: float) -> float:
    p = max(p, 1e-15)
    return -10.0 * np.log10(p)


# ---------- Core network model ----------
@dataclass
class ScatteringNetwork:
    """Linear multi-port network of block-diagonal devices with bidirectional connections.

    Waves: a = incoming, b = outgoing (scattered).
      b = S a
      a = C b + s     (C sets interconnections; s is external source waves)

    => (I - S C) b = S s  => b = (I - S C)^(-1) S s
       a = C b + s
    """
    S_blocks: List[np.ndarray]
    N: int = field(init=False)
    S: np.ndarray = field(init=False)
    C: np.ndarray = field(init=False)

    # variable (trainable) edges; each is bidirectional: a_p = r e^{jphi} b_q and a_q = r e^{jphi} b_p
    var_edges: List[Tuple[int, int]] = field(default_factory=list)
    edge_r: List[float] = field(default_factory=list)
    edge_phi: List[float] = field(default_factory=list)
    # fixed edges
    fixed_edges: List[Tuple[int, int, complex]] = field(default_factory=list)

    # computed externals (rows of C that remain 0)
    external_ports: Optional[List[int]] = None

    def __post_init__(self):
        dims = [int(B.shape[0]) for B in self.S_blocks]
        assert all(B.shape[0] == B.shape[1] for B in self.S_blocks), "Each S block must be square"
        self.N = int(np.sum(dims))
        self.S = np.zeros((self.N, self.N), dtype=np.complex128)
        off = 0
        for B in self.S_blocks:
            k = B.shape[0]
            self.S[off:off+k, off:off+k] = B
            off += k
        self.C = np.zeros((self.N, self.N), dtype=np.complex128)

    def add_connection(self, p: int, q: int, amp: float = 1.0, phi: float = 0.0, trainable: bool = True):
        assert 0 <= p < self.N and 0 <= q < self.N and p != q
        coeff = amp * np.exp(1j * phi)
        self.C[p, q] = coeff
        self.C[q, p] = coeff
        if trainable:
            self.var_edges.append((p, q))
            self.edge_r.append(float(amp))
            self.edge_phi.append(float(phi))
        else:
            self.fixed_edges.append((p, q, coeff))

    def set_external_from_unconnected(self):
        rows_zero = np.isclose(np.sum(np.abs(self.C), axis=1), 0.0)
        self.external_ports = [int(i) for i, flag in enumerate(rows_zero) if flag]

    # ---- Linear operators ----
    def _update_var_phases(self, phi_vec: np.ndarray):
        # write variable edges
        for i, (p, q) in enumerate(self.var_edges):
            r = self.edge_r[i]
            coeff = r * np.exp(1j * phi_vec[i])
            self.C[p, q] = coeff
            self.C[q, p] = coeff
        # restore fixed edges
        for (p, q, coeff) in self.fixed_edges:
            self.C[p, q] = coeff
            self.C[q, p] = coeff

    def M_operator(self) -> np.ndarray:
        """Return M = (I - S C)^(-1) S mapping s -> b for arbitrary s."""
        I = np.eye(self.N, dtype=np.complex128)
        try:
            Minv = np.linalg.inv(I - self.S @ self.C)
        except np.linalg.LinAlgError:
            Minv = np.linalg.pinv(I - self.S @ self.C)
        return Minv @ self.S

    # ---- Effective network transfer ----
    def T_net(self, in_ports: Sequence[int], out_ports: Sequence[int]) -> np.ndarray:
        """Return effective transfer matrix from in_ports (sources) to out_ports (outgoing b)."""
        if self.external_ports is None:
            self.set_external_from_unconnected()
        P_in = np.zeros((self.N, len(in_ports)), dtype=np.complex128)
        for j, p in enumerate(in_ports):
            P_in[p, j] = 1.0
        P_out = np.zeros((len(out_ports), self.N), dtype=np.complex128)
        for i, p in enumerate(out_ports):
            P_out[i, p] = 1.0
        M = self.M_operator()   # b = M s
        return P_out @ M @ P_in

    # ---- Solve for a given source vector s (arbitrary multi-port) ----
    def solve_for_s(self, s: np.ndarray) -> Dict[str, np.ndarray]:
        I = np.eye(self.N, dtype=np.complex128)
        try:
            b = np.linalg.solve(I - self.S @ self.C, self.S @ s)
        except np.linalg.LinAlgError:
            b = np.linalg.lstsq(I - self.S @ self.C, self.S @ s, rcond=None)[0]
        a = self.C @ b + s
        return {"a": a, "b": b}


# ---------- Convenience blocks (example PDK primitives) ----------
def symmetric_3db_coupler(loss_db: float = 0.0) -> np.ndarray:
    """Ideal symmetric 3 dB coupler (4x4 S) with optional excess loss."""
    a = db_to_amp(loss_db)
    t = a / np.sqrt(2.0)
    k = 1j * a / np.sqrt(2.0)
    S = np.zeros((4, 4), dtype=np.complex128)
    # left->right
    S[0, 2] = t; S[0, 3] = k
    S[1, 2] = k; S[1, 3] = t
    # right->left
    S[2, 0] = t; S[3, 0] = k
    S[2, 1] = k; S[3, 1] = t
    return S

def build_mzi_network(arm_amp: float = 0.98, loss_db_cpl: float = 0.1) -> ScatteringNetwork:
    """Two 3 dB couplers with two tunable arms (bidirectional links)."""
    S_blocks = [symmetric_3db_coupler(loss_db_cpl),
                symmetric_3db_coupler(loss_db_cpl)]
    net = ScatteringNetwork(S_blocks)
    c1 = lambda i: i
    c2 = lambda i: 4 + i
    # Internal arms (trainable phases)
    net.add_connection(p=c2(0), q=c1(2), amp=arm_amp, phi=0.0, trainable=True)
    net.add_connection(p=c2(1), q=c1(3), amp=arm_amp, phi=0.0, trainable=True)
    net.set_external_from_unconnected()
    return net


# ---------- Optimizer that targets the SVD upper bound ----------
@dataclass
class SVDBoundOptimizer:
    """Maximize sigma_max^2(T_net(phi)) by tuning internal phases phi, then recover the SVD-optimal input drive."""
    net: ScatteringNetwork
    in_ports: Sequence[int]
    out_ports: Sequence[int]

    def svd_value_and_vec(self, phi: Optional[np.ndarray] = None) -> Tuple[float, np.ndarray, np.ndarray]:
        """Return (sigma_max^2, v_opt, u_opt) for current or provided phases."""
        if phi is not None:
            self.net._update_var_phases(phi)
        T = self.net.T_net(self.in_ports, self.out_ports)  # shape (nout, nin)
        # SVD on effective transfer
        U, s, Vh = np.linalg.svd(T, full_matrices=False)
        sigma2 = float(s[0] ** 2)
        v = Vh.conj().T[:, 0]    # input vector on in_ports (unit-norm)
        u = U[:, 0]              # output singular vector (not used here, but may be useful)
        return sigma2, v, u

    def objective(self, phi: np.ndarray) -> float:
        # We minimize negative sigma^2 to *maximize* sigma^2
        sigma2, _, _ = self.svd_value_and_vec(phi)
        return float(-sigma2)

    def optimize_phases(self,
                        phi0: Optional[np.ndarray] = None,
                        maxiter: int = 400,
                        n_restarts: int = 8,
                        seed: int = 1) -> Dict[str, np.ndarray]:
        num = len(self.net.var_edges)
        if phi0 is None:
            rng = np.random.default_rng(seed)
            phi0 = rng.uniform(-np.pi, np.pi, size=(num,))
        best = {"phi": phi0.copy(), "val": self.objective(phi0)}
        # Try SciPy if available
        used_scipy = False
        try:
            from scipy.optimize import minimize
            used_scipy = True
            for r in range(n_restarts):
                x0 = phi0 + (np.random.rand(num) - 0.5) * 0.5
                res = minimize(self.objective, x0, method="Nelder-Mead",
                               options={"maxiter": maxiter, "xatol": 1e-5, "fatol": 1e-5, "disp": False})
                if res.fun < best["val"]:
                    best["val"] = float(res.fun)
                    best["phi"] = res.x.copy()
        except Exception:
            pass
        if not used_scipy:
            rng = np.random.default_rng(seed)
            for _ in range(max(2000, 300 * max(1, num))):
                trial = rng.uniform(-np.pi, np.pi, size=(num,))
                val = self.objective(trial)
                if val < best["val"]:
                    best["val"] = float(val)
                    best["phi"] = trial.copy()

        # Set the best phases and return the SVD bound and vector
        self.net._update_var_phases(best["phi"])
        sigma2, v_opt, _ = self.svd_value_and_vec()  # at optimum phases
        return {"phi_opt": best["phi"], "sigma2_opt": np.array([sigma2]), "v_in_opt": v_opt}

    def achieved_with_svd_drive(self, v_in: np.ndarray) -> Dict[str, float]:
        """Inject the SVD-optimal drive across in_ports and measure power on out_ports and total external."""
        # Build s (source) as zeros + drive on in_ports
        s = np.zeros(self.net.N, dtype=np.complex128)
        for j, p in enumerate(self.in_ports):
            s[p] = v_in[j]  # assume unit-norm vector; total input power = 1
        sol = self.net.solve_for_s(s)
        b = sol["b"]

        out_idx = np.array(self.out_ports, dtype=int)
        P_tgt = float(np.sum(np.abs(b[out_idx])**2))

        if self.net.external_ports is None:
            self.net.set_external_from_unconnected()
        ext_idx = np.array(self.net.external_ports, dtype=int)
        P_ext = float(np.sum(np.abs(b[ext_idx])**2))
        loss = 1.0 - P_ext
        return {"throughput_to_outputs": P_tgt, "total_external_power": P_ext, "internal_loss": loss}


# ---------- Example / Demo (MZI) ----------
if __name__ == "__main__":
    # Build an MZI (two couplers + two tunable arms)
    net = build_mzi_network(arm_amp=0.98, loss_db_cpl=0.1)

    # Choose controllable input port set and measured outputs set
    # Here: drive both left inputs (c1 ports 0 and 1), collect at the two right outputs (c2 ports 6 and 7).
    in_ports  = [0, 1]      # ports you can coherently drive
    out_ports = [6, 7]      # ports you "count" (you can also choose just [7], etc.)

    opt = SVDBoundOptimizer(net, in_ports, out_ports)

    # ---- BEFORE (initial phases) ----
    phi0 = np.zeros(len(net.var_edges))   # try a neutral start; feel free to randomize
    net._update_var_phases(phi0)
    sigma2_0, v0, _ = opt.svd_value_and_vec()    # SVD bound at start
    before = opt.achieved_with_svd_drive(v0)

    print("=== BEFORE ===")
    print(f"phi0 (rad): {phi0}")
    print(f"SVD_bound (sigma^2): {sigma2_0:.6f}  => bound IL: {db10_from_power(sigma2_0):.3f} dB")
    print(f"achieved throughput to outputs (with SVD drive): {before['throughput_to_outputs']:.6f} "
          f"({db10_from_power(before['throughput_to_outputs']):.3f} dB)")
    print(f"total external power: {before['total_external_power']:.6f} "
          f"({db10_from_power(before['total_external_power']):.3f} dB)")
    print(f"internal loss: {before['internal_loss']:.6f}")

    # ---- OPTIMIZE PHASES to maximize the SVD bound ----
    res = opt.optimize_phases(phi0=phi0, maxiter=400, n_restarts=8, seed=42)
    phi_star = res["phi_opt"]
    sigma2_star = float(res["sigma2_opt"][0])
    v_star = res["v_in_opt"]

    after = opt.achieved_with_svd_drive(v_star)

    print("\n=== AFTER (optimized phases) ===")
    print(f"phi_opt (rad): {phi_star}")
    print(f"SVD_bound (sigma^2): {sigma2_star:.6f}  => bound IL: {db10_from_power(sigma2_star):.3f} dB")
    print(f"achieved throughput to outputs (with SVD drive): {after['throughput_to_outputs']:.6f} "
          f"({db10_from_power(after['throughput_to_outputs']):.3f} dB)")
    print(f"total external power: {after['total_external_power']:.6f} "
          f"({db10_from_power(after['total_external_power']):.3f} dB)")
    print(f"internal loss: {after['internal_loss']:.6f}")

    # ---- Improvement summary ----
    print("\n=== Improvement ===")
    print(f"+ SVD_bound: {sigma2_star - sigma2_0:+.6f} "
          f"({db10_from_power(sigma2_star) - db10_from_power(sigma2_0):+.3f} dB)")
    print(f"+ throughput_to_outputs: {after['throughput_to_outputs'] - before['throughput_to_outputs']:+.6f} "
          f"({db10_from_power(after['throughput_to_outputs']) - db10_from_power(before['throughput_to_outputs']):+.3f} dB)")
    print(f"- internal_loss: {before['internal_loss'] - after['internal_loss']:+.6f}")