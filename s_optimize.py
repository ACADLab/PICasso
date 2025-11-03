# s_optimize.py
# Self-contained utilities to optimize optical loss (maximize transmission) from scattering matrices.
# Author: ChatGPT (PIC researcher mode)

from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Sequence

# --- Utils ---

def db_to_amp(loss_db: float) -> float:
    '''Convert excess loss in dB to field amplitude scale factor (one-way).'''
    return 10 ** (-loss_db / 20.0)

def amp_to_db(amp: float) -> float:
    '''Convert field amplitude scale factor to dB (one-way).'''
    return -20.0 * np.log10(max(amp, 1e-12))

def complex2(x: complex) -> float:
    return (x.real**2 + x.imag**2)

# --- Device-level optimizer (no topology; best excitation) ---

@dataclass
class DeviceOptimizer:
    S: np.ndarray  # Full scattering matrix (NxN)
    input_ports: Sequence[int]   # subset of ports we can excite
    output_ports: Sequence[int]  # subset of ports we care to collect power from

    def optimal_excitation(self) -> Dict[str, np.ndarray]:
        '''
        Returns the unit-norm input vector on `input_ports` that maximizes power in `output_ports`.
        This is the dominant right-singular vector of the transfer submatrix T = S[out, in].
        '''
        S = np.asarray(self.S, dtype=np.complex128)
        in_idx = np.array(self.input_ports, dtype=int)
        out_idx = np.array(self.output_ports, dtype=int)

        T = S[np.ix_(out_idx, in_idx)]
        # SVD: T = U Σ V^H
        U, s, Vh = np.linalg.svd(T, full_matrices=False)
        v_opt = Vh.conj().T[:, 0]               # right singular vector (unit norm)
        sigma_max = s[0]                        # singular value
        eta = float(sigma_max**2)               # max power transfer (0..1) for unit-norm input
        loss = 1.0 - eta

        # Embed excitation back into full port vector a (incoming waves)
        N = S.shape[0]
        a = np.zeros(N, dtype=np.complex128)
        a[in_idx] = v_opt  # unit power distributed across chosen input ports

        # Predicted outgoing power at outputs for the optimal excitation
        b = S @ a
        P_out = float(np.sum(np.abs(b[out_idx])**2))
        # Numerical diff could occur; clamp
        P_out = float(np.clip(P_out, 0.0, 1.0))

        return {
            "v_opt_in": a,              # length-N input wave (unit-norm across in-ports)
            "eta_max": np.array([eta]), # scalar in array for convenience
            "loss_min": np.array([loss]),
            "b_out": b,
            "P_out": np.array([P_out]),
        }

# --- Circuit-level network model using connection matrix a = C b + s  ---
# Solve b = S a = S (C b + s) => (I - S C) b = S s  => b = (I - S C)^{-1} S s

@dataclass
class ScatteringNetwork:
    S_blocks: List[np.ndarray]          # list of component scattering matrices (k_i x k_i)
    external_ports: Optional[List[int]] = None
    N: int = field(init=False)
    S: np.ndarray = field(init=False)
    C: np.ndarray = field(init=False)
    # Store variable edges for optimization: list of (p, q) indices, with magnitude r and phase phi
    var_edges: List[Tuple[int, int]] = field(default_factory=list)
    edge_r: List[float] = field(default_factory=list)
    edge_phi: List[float] = field(default_factory=list)  # current values
    fixed_edges: List[Tuple[int, int, complex]] = field(default_factory=list)  # (p, q, coeff)

    def __post_init__(self):
        dims = [int(B.shape[0]) for B in self.S_blocks]
        assert all(B.shape[0] == B.shape[1] for B in self.S_blocks), "Each S block must be square"
        self.N = int(np.sum(dims))
        # Block diagonal S
        self.S = np.zeros((self.N, self.N), dtype=np.complex128)
        offset = 0
        for B in self.S_blocks:
            k = B.shape[0]
            self.S[offset:offset+k, offset:offset+k] = B
            offset += k
        # Empty connection matrix
        self.C = np.zeros((self.N, self.N), dtype=np.complex128)

    def add_connection(self, p: int, q: int, amp: float = 1.0, phi: float = 0.0, trainable: bool = True):
        '''Connect port p to q bidirectionally: a_p = coeff * b_q and a_q = coeff * b_p.
        coeff = amp * exp(1j*phi). If trainable, phi becomes an optimizable parameter.
        '''
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
        '''Define external ports = those whose 'a' is not fully determined by C (i.e., row of C is all zeros).'''
        rows_zero = np.isclose(np.sum(np.abs(self.C), axis=1), 0.0)
        self.external_ports = [int(i) for i, flag in enumerate(rows_zero) if flag]

    def _set_var_phases(self, phi_vec: np.ndarray):
        '''Update phases for variable edges in C using current phi_vec (in radians).'''
        # Reset the variable elements in C according to fixed edge magnitudes
        for i, (p, q) in enumerate(self.var_edges):
            r = self.edge_r[i]
            coeff = r * np.exp(1j * phi_vec[i])
            self.C[p, q] = coeff
            self.C[q, p] = coeff
        # Re-apply fixed edges to be safe
        for (p, q, coeff) in self.fixed_edges:
            self.C[p, q] = coeff
            self.C[q, p] = coeff

    def solve(self, src_port: int, src_amp: complex = 1.0) -> Dict[str, np.ndarray]:
        '''Solve for b, a, given a single-port source on an external port.'''
        assert 0 <= src_port < self.N
        I = np.eye(self.N, dtype=np.complex128)
        s = np.zeros(self.N, dtype=np.complex128)
        s[src_port] = src_amp
        try:
            b = np.linalg.solve(I - self.S @ self.C, self.S @ s)
        except np.linalg.LinAlgError:
            # Use least-squares if near-singular
            b = np.linalg.lstsq(I - self.S @ self.C, self.S @ s, rcond=None)[0]
        a = self.C @ b + s
        return {"a": a, "b": b, "src_power": np.abs(src_amp)**2}

    def power_on_ports(self, waves: np.ndarray, ports: Sequence[int]) -> float:
        idx = np.array(ports, dtype=int)
        return float(np.sum(np.abs(waves[idx])**2))

    def total_external_power(self, b: np.ndarray) -> float:
        if self.external_ports is None:
            self.set_external_from_unconnected()
        return self.power_on_ports(b, self.external_ports)

    def objective(self, phi_vec: np.ndarray, src_port: int, target_ports: Sequence[int], w_reflect: float = 0.0) -> float:
        '''Negative throughput objective (for minimization): maximize power to target, penalize reflection if desired.
        Returns real scalar.
        '''
        self._set_var_phases(phi_vec)
        sol = self.solve(src_port)
        b = sol["b"]
        # Throughput to targets
        P_tgt = self.power_on_ports(b, target_ports)
        # Optional penalty on reflection back to source
        P_ref = float(np.abs(b[src_port])**2)
        # Maximize P_tgt, minimize P_ref
        return float(-(P_tgt - w_reflect * P_ref))

    def optimize_phases(self,
                        src_port: int,
                        target_ports: Sequence[int],
                        phi0: Optional[np.ndarray] = None,
                        w_reflect: float = 0.0,
                        maxiter: int = 300,
                        n_restarts: int = 6,
                        seed: int = 1) -> Dict[str, np.ndarray]:
        '''Optimize variable connection phases to maximize power in target ports.
        Uses SciPy's Nelder-Mead if available; otherwise random-restart grid search.
        Returns best phases, best throughput, and final b.
        '''
        num_vars = len(self.var_edges)
        if phi0 is None:
            rng = np.random.default_rng(seed)
            phi0 = rng.uniform(-np.pi, np.pi, size=(num_vars,))

        def obj(phi):
            return self.objective(phi, src_port=src_port, target_ports=target_ports, w_reflect=w_reflect)

        best = {"phi": None, "val": +np.inf}

        # Try SciPy first
        try:
            from scipy.optimize import minimize
            for r in range(n_restarts):
                x0 = phi0 + (np.random.rand(num_vars) - 0.5) * 0.5  # small jitter
                res = minimize(obj, x0, method="Nelder-Mead", options={"maxiter": maxiter, "xatol": 1e-5, "fatol": 1e-5, "disp": False})
                if res.fun < best["val"]:
                    best["val"] = float(res.fun)
                    best["phi"] = res.x.copy()
        except Exception:
            # Fallback coarse random search
            rng = np.random.default_rng(seed)
            for _ in range(max(2000, 200 * num_vars)):
                trial = rng.uniform(-np.pi, np.pi, size=(num_vars,))
                val = obj(trial)
                if val < best["val"]:
                    best["val"] = float(val)
                    best["phi"] = trial.copy()

        # Final solve with best phases
        self._set_var_phases(best["phi"])
        sol = self.solve(src_port)
        b = sol["b"]
        P_tgt = self.power_on_ports(b, target_ports)
        P_ext = self.total_external_power(b)
        loss = 1.0 - P_ext  # internal optical loss
        return {
            "phi_opt": best["phi"],
            "throughput_to_target": np.array([P_tgt]),
            "total_external_power": np.array([P_ext]),
            "internal_loss": np.array([loss]),
            "waves_b": b,
        }

# --- Convenience builders ---

def symmetric_3db_coupler(loss_db: float = 0.0) -> np.ndarray:
    '''Ideal symmetric 3 dB directional coupler (4x4 S), optional excess loss (applied uniformly as field amp).'''
    a = db_to_amp(loss_db)
    t = a / np.sqrt(2.0)
    k = 1j * a / np.sqrt(2.0)
    S = np.zeros((4, 4), dtype=np.complex128)
    # left -> right
    S[0, 2] = t; S[0, 3] = k
    S[1, 2] = k; S[1, 3] = t
    # right -> left
    S[2, 0] = t; S[3, 0] = k
    S[2, 1] = k; S[3, 1] = t
    # no reflections
    return S

def mzi_two_couplers(loss_db_cpl: float = 0.0) -> List[np.ndarray]:
    '''Return [S_c1, S_c2] for a Mach-Zehnder Interferometer made of two identical 3dB couplers.'''
    return [symmetric_3db_coupler(loss_db_cpl), symmetric_3db_coupler(loss_db_cpl)]

# --- Demo builders ---

def build_mzi_network(arm_amp: float = 0.99, loss_db_cpl: float = 0.1) -> ScatteringNetwork:
    '''Build a simple MZI: two 3dB couplers with two tunable-phase arms of amplitude arm_amp.
    Global port order: [c1:0..3, c2:0..3]
      External input(s): c1 ports 0,1
      External output(s): c2 ports 2,3
      Internal connections:
         c1.2 -> c2.0 (upper arm) with phase phi1
         c1.3 -> c2.1 (lower arm) with phase phi2
    '''
    S_blocks = mzi_two_couplers(loss_db_cpl=loss_db_cpl)
    net = ScatteringNetwork(S_blocks=S_blocks)

    # Index helpers
    # Coupler 1 ports: 0..3  ; Coupler 2 ports: 4..7
    c1 = lambda i: i
    c2 = lambda i: 4 + i

    # Add trainable internal arms with amplitude < 1 for propagation loss
    net.add_connection(p=c2(0), q=c1(2), amp=arm_amp, phi=0.0, trainable=True)  # a_c2.0 = r e^{j phi1} b_c1.2
    net.add_connection(p=c2(1), q=c1(3), amp=arm_amp, phi=0.0, trainable=True)  # a_c2.1 = r e^{j phi2} b_c1.3

    # Set external to unconnected rows automatically
    net.set_external_from_unconnected()
    return net

# --- Pretty print helpers ---

def summarize_solution(tag: str, res: Dict):
    s = []
    s.append(f"=== {tag} ===")
    for k, v in res.items():
        if isinstance(v, np.ndarray):
            if v.ndim == 1 and v.size == 1:
                s.append(f"{k}: {float(np.real(v[0])):.6f}")
            else:
                s.append(f"{k}: shape {v.shape}")
        else:
            s.append(f"{k}: {v}")
    return "\n".join(s)