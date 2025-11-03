# gf_optimize.py
# Optimize optical loss / delivery on a GDSFactory circuit using SAX evaluation.
from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple, Callable, Optional, Sequence

# Optional SciPy
try:
    from scipy.optimize import minimize
    _HAVE_SCIPY = True
except Exception:
    _HAVE_SCIPY = False

# --- Helper math ---
def db10_from_power(p: float) -> float:
    p = max(float(p), 1e-15)
    return -10.0 * np.log10(p)

def svd_bound(T: np.ndarray) -> Tuple[float, np.ndarray, np.ndarray]:
    # T shape = (nout, nin)
    U, s, Vh = np.linalg.svd(T, full_matrices=False)
    sigma2 = float(s[0] ** 2)
    v = Vh.conj().T[:, 0]  # input vector (unit-norm on in-ports)
    u = U[:, 0]
    return sigma2, v, u

# --- SAX <-> GDSFactory glue ---
@dataclass
class SaxCircuit:
    """Thin wrapper that evaluates S for a GDSFactory netlist via SAX.

    build_fn must return a callable `circuit(params)` compatible with SAX:
      circuit(params) -> dict of scattering entries or dense S.
    `port_list` is the ordered list of top-level port names for S row/col order.
    """
    circuit_fn: Callable[[Dict[str, float]], Dict[str, complex] | np.ndarray]
    port_list: List[str]                           # global port order for S

    def S_dense(self, params: Dict[str, float]) -> np.ndarray:
        from sax import sdense
        Sd = self.circuit_fn(params)
        return sdense(Sd, ports=self.port_list)

    def submatrix(self,
                  S: np.ndarray,
                  in_ports: Sequence[str],
                  out_ports: Sequence[str]) -> Tuple[np.ndarray, List[int], List[int]]:
        idx = {p: i for i, p in enumerate(self.port_list)}
        im = [idx[p] for p in in_ports]
        om = [idx[p] for p in out_ports]
        return S[np.ix_(om, im)], im, om

# --- Objective builders ---
def objective_power_to_targets(S: np.ndarray,
                               port_list: List[str],
                               in_ports: Sequence[str],
                               out_ports: Sequence[str],
                               drive: str = "svd") -> float:
    """Return negative delivered power to out_ports, for minimization.
    drive="svd": use SVD-optimal multi-port drive on in_ports.
    drive="single:<name>": drive one port with 1.0 amplitude.
    """
    T, im, om = SaxCircuit(lambda _: None, port_list).submatrix(S, in_ports, out_ports)
    if drive == "svd":
        sigma2, _, _ = svd_bound(T)
        return -sigma2  # maximize delivered power
    elif drive.startswith("single:"):
        sel = drive.split(":", 1)[1]
        if sel not in in_ports:
            raise ValueError(f"drive port {sel} not among in_ports")
        e = np.zeros((len(in_ports),), dtype=np.complex128)
        e[in_ports.index(sel)] = 1.0
        P = float(np.sum(np.abs(T @ e) ** 2))
        return -P
    else:
        raise ValueError("drive must be 'svd' or 'single:<port>'")

def objective_reflection(S: np.ndarray,
                         port_list: List[str],
                         in_ports: Sequence[str],
                         drive: str = "single") -> float:
    """Return reflection at driven in-port(s) (0..1), to minimize."""
    idx = {p: i for i, p in enumerate(port_list)}
    if drive == "single":
        if len(in_ports) != 1:
            raise ValueError("reflection objective with 'single' expects exactly one in_port")
        i = idx[in_ports[0]]
        return float(np.abs(S[i, i]) ** 2)
    elif drive == "svd":
        # reflect under SVD input vector: build T and push back to full space
        # Approximate via power on in_ports rows from T * v (ignores cross-coupling outside T)
        # If you need exact reflection to any in-port (same label), consider full-wave solve w/ source vector.
        return 0.0  # often we combine as a penalty only; set 0 if not computed explicitly
    else:
        raise ValueError("drive must be 'single' or 'svd'")

def objective_band_flatness(Ss: List[np.ndarray],
                            port_list: List[str],
                            in_ports: Sequence[str],
                            out_ports: Sequence[str],
                            drive: str = "svd") -> float:
    """Minimize variance of delivered power across a wavelength band."""
    vals = []
    for S in Ss:
        vals.append(-objective_power_to_targets(S, port_list, in_ports, out_ports, drive=drive))  # delivered power
    vals = np.array(vals)
    return float(np.var(vals))

# --- Master optimizer ---
@dataclass
class NetlistOptimizer:
    sax_circuit: SaxCircuit
    in_ports: Sequence[str]
    out_ports: Sequence[str]
    wl_grid: np.ndarray                             # e.g., np.linspace(1.54e-6, 1.56e-6, 31)
    param_names: List[str]                          # names in params dict to optimize
    bounds: Dict[str, Tuple[float, float]]          # box bounds per param (inclusive)
    fixed_params: Optional[Dict[str, float]] = None # other constant params for the model

    def evaluate_S(self, params: Dict[str, float]) -> List[np.ndarray]:
        S_list = []
        for wl in self.wl_grid:
            p = dict(self.fixed_params or {})
            p.update(params)
            p["wavelength"] = float(wl)
            S = self.sax_circuit.S_dense(p)
            S_list.append(S)
        return S_list

    def loss(self,
             x: np.ndarray,
             weights: Dict[str, float] = {"deliver": 1.0, "reflect": 0.0, "flat": 0.0},
             drive: str = "svd") -> float:
        params = {k: float(v) for k, v in zip(self.param_names, x)}
        Ss = self.evaluate_S(params)
        # Main delivery objective at center wavelength
        S0 = Ss[len(Ss)//2]
        J_deliver = objective_power_to_targets(S0, self.sax_circuit.port_list,
                                               self.in_ports, self.out_ports, drive=drive)
        # Reflection penalty at center wavelength
        J_refl = objective_reflection(S0, self.sax_circuit.port_list, self.in_ports,
                                      drive="single" if drive.startswith("single") else "svd")
        # Band flatness (variance)
        J_flat = objective_band_flatness(Ss, self.sax_circuit.port_list,
                                         self.in_ports, self.out_ports, drive=drive)
        # Weighted sum
        return (weights.get("deliver", 1.0) * J_deliver +
                weights.get("reflect", 0.0) * J_refl +
                weights.get("flat", 0.0) * J_flat)

    def optimize(self,
                 x0: np.ndarray,
                 weights: Dict[str, float] = {"deliver": 1.0, "reflect": 0.0, "flat": 0.0},
                 drive: str = "svd",
                 maxiter: int = 400,
                 n_restarts: int = 6,
                 seed: int = 1) -> Dict[str, object]:
        # Box projection helper
        lows = np.array([self.bounds[n][0] for n in self.param_names], dtype=float)
        highs = np.array([self.bounds[n][1] for n in self.param_names], dtype=float)

        def proj(z):
            return np.minimum(np.maximum(z, lows), highs)

        rng = np.random.default_rng(seed)
        best = {"x": proj(np.array(x0, dtype=float)), "val": np.inf}

        def fun(z):
            return self.loss({k: float(v) for k, v in zip(self.param_names, z)} if isinstance(z, dict) else z,
                             weights=weights, drive=drive)

        # SciPy first
        if _HAVE_SCIPY:
            for r in range(n_restarts):
                xr = proj(np.array(x0, dtype=float) + 0.2*(rng.random(len(x0))-0.5))
                res = minimize(lambda z: self.loss(z, weights=weights, drive=drive),
                               xr, method="Nelder-Mead",
                               options={"maxiter": maxiter, "xatol":1e-5, "fatol":1e-5, "disp": False})
                if res.fun < best["val"]:
                    best["val"], best["x"] = float(res.fun), proj(res.x)
        else:
            # Fallback random search
            for _ in range(max(2000, 300*len(x0))):
                xr = proj(lows + (highs-lows)*rng.random(len(x0)))
                val = self.loss(xr, weights=weights, drive=drive)
                if val < best["val"]:
                    best["val"], best["x"] = float(val), xr

        # Return details + metrics at best
        pars = {k: float(v) for k, v in zip(self.param_names, best["x"])}
        Ss = self.evaluate_S(pars)
        S0 = Ss[len(Ss)//2]
        # Best SVD bound & achieved with SVD drive at center
        T, _, _ = SaxCircuit(lambda _: None, self.sax_circuit.port_list).submatrix(S0, self.in_ports, self.out_ports)
        sigma2, v, _ = svd_bound(T)
        # Achieved power with that drive
        P_ach = float(np.sum(np.abs(T @ v)**2))
        return {
            "x_opt": best["x"], "params_opt": pars, "loss": best["val"],
            "sigma2_center": sigma2, "achieved_center": P_ach,
            "insertion_loss_dB_center": db10_from_power(P_ach),
        }