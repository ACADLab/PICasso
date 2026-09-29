from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Sequence, Callable, Any

# Optional SciPy
try:
    from scipy.optimize import minimize
    _HAVE_SCIPY = True
except Exception:
    _HAVE_SCIPY = False


# =========================
# Utilities
# =========================
def svd_bound(T: np.ndarray) -> float:
    # Largest singular value squared (power)
    s = np.linalg.svd(T, compute_uv=False)
    return float(s[0] ** 2)

def submatrix(S: np.ndarray, port_list: List[str],
              in_ports: Sequence[str], out_ports: Sequence[str]) -> np.ndarray:
    idx = {p: i for i, p in enumerate(port_list)}
    im = [idx[p] for p in in_ports]
    om = [idx[p] for p in out_ports]
    return S[np.ix_(om, im)]

def db10_from_power(p: float) -> float:
    p = max(float(p), 1e-15)
    return -10.0 * np.log10(p)


# =========================
# Evaluator glue (SAX)
# =========================
def make_sax_evaluator(netlist: Dict[str, Any],
                       models: Dict[str, Callable[..., Any]],
                       port_list: List[str]) -> Callable[[Dict[str, float]], np.ndarray]:
    """
    Returns: get_S(params) -> dense S (np.ndarray) using SAX.
    You supply 'models' for your PDK; we convert to sdense with 'port_list' ordering.
    """
    import sax
    # Wrap models to SAX callable interface
    sax_models = {}
    for name, fn in models.items():
        def _wrap(f):
            def g(**kwargs):
                Sd = f(kwargs)  # return sax.sdict or dict-compatible for sax
                # If already sdict, keep; else convert {("p","q"): val} with known ports
                if isinstance(Sd, dict) and "ports" in Sd and "S" in Sd:
                    return sax.sdict(Sd["S"], ports=Sd["ports"])
                return Sd
            return g
        sax_models[name] = _wrap(fn)

    circ = sax.circuit(netlist=netlist, models=sax_models)
    from sax import sdense

    def get_S(params: Dict[str, float]) -> np.ndarray:
        Sd = circ(**params)
        return sdense(Sd, ports=port_list)
    return get_S


# =========================
# Tunable parameter spec
# =========================
@dataclass
class Tunable:
    inst: str              # instance name in netlist["instances"]
    key: str               # parameter key inside instance settings (e.g., "phi", "kappa")
    lo: float              # lower bound
    hi: float              # upper bound
    x0: float              # initial value


# =========================
# Netlist param I/O
# =========================
def read_params_from_netlist(netlist: Dict[str, Any], tunables: List[Tunable]) -> np.ndarray:
    xs = []
    for t in tunables:
        v = None
        inst = netlist["instances"].get(t.inst, {})
        settings = inst.get("settings", inst.get("params", {}))
        if t.key in settings:
            v = float(settings[t.key])
        else:
            v = float(t.x0)
        xs.append(v)
    return np.array(xs, dtype=float)

def write_params_to_netlist(netlist: Dict[str, Any], tunables: List[Tunable], x: np.ndarray) -> Dict[str, Any]:
    nl = {**netlist, "instances": {k: dict(v) for k, v in netlist["instances"].items()}}
    for t, val in zip(tunables, x):
        inst = nl["instances"].setdefault(t.inst, {})
        # normalize bucket for params/settings
        if "settings" not in inst and "params" in inst:
            inst["settings"] = dict(inst["params"])
        inst.setdefault("settings", {})
        inst["settings"][t.key] = float(val)
    return nl


# =========================
# Objective functions
# =========================
def objective_delivery(get_S: Callable[[Dict[str, float]], np.ndarray],
                       port_list: List[str],
                       in_ports: Sequence[str],
                       out_ports: Sequence[str],
                       params: Dict[str, float],
                       drive: str = "svd") -> float:
    """Return negative delivered power to out_ports for minimization."""
    S = get_S(params)
    T = submatrix(S, port_list, in_ports, out_ports)
    if drive == "svd":
        return -svd_bound(T)
    elif drive.startswith("single:"):
        sel = drive.split(":", 1)[1]
        e = np.zeros((len(in_ports),), dtype=np.complex128)
        e[in_ports.index(sel)] = 1.0
        P = float(np.sum(np.abs(T @ e) ** 2))
        return -P
    else:
        raise ValueError("drive must be 'svd' or 'single:<port>'")

def objective_flatness(get_Ss: Callable[[Dict[str, float]], List[np.ndarray]],
                       port_list: List[str],
                       in_ports: Sequence[str],
                       out_ports: Sequence[str],
                       params: Dict[str, float],
                       drive: str = "svd") -> float:
    """Variance of delivered power across wavelength grid (minimize)."""
    Ss = get_Ss(params)
    vals = []
    for S in Ss:
        T = submatrix(S, port_list, in_ports, out_ports)
        if drive == "svd":
            vals.append(svd_bound(T))
        else:
            sel = drive.split(":", 1)[1]
            e = np.zeros((len(in_ports),), dtype=np.complex128)
            e[in_ports.index(sel)] = 1.0
            vals.append(float(np.sum(np.abs(T @ e) ** 2)))
    return float(np.var(np.array(vals)))

def objective_reflection(get_S: Callable[[Dict[str, float]], np.ndarray],
                         port_list: List[str],
                         in_ports: Sequence[str],
                         params: Dict[str, float],
                         drive: str = "single") -> float:
    """Reflection at driven in-port(s) (only meaningful for single-port drive)."""
    if drive != "single":
        return 0.0
    if len(in_ports) != 1:
        raise ValueError("reflection objective with 'single' expects exactly one in_port")
    idx = {p: i for i, p in enumerate(port_list)}
    i = idx[in_ports[0]]
    S = get_S(params)
    return float(np.abs(S[i, i]) ** 2)


# =========================
# Optimizer
# =========================
def optimize_netlist(
    netlist: Dict[str, Any],
    tunables: List[Tunable],
    port_list: List[str],
    in_ports: Sequence[str],
    out_ports: Sequence[str],
    get_S: Optional[Callable[[Dict[str, float]], np.ndarray]] = None,
    get_Ss: Optional[Callable[[Dict[str, float]], List[np.ndarray]]] = None,
    models: Optional[Dict[str, Callable[..., Any]]] = None,
    wl_grid: Optional[np.ndarray] = None,
    weights: Dict[str, float] = {"deliver": 1.0, "flat": 0.0, "reflect": 0.0},
    drive: str = "svd",
    x0: Optional[np.ndarray] = None,
    maxiter: int = 400,
    n_restarts: int = 6,
    seed: int = 1,
) -> Dict[str, Any]:
    """
    Core entry point.
    - If get_S / get_Ss are not provided, we build them from SAX using 'models' and 'wl_grid'.
    - Returns dict with optimized x, metrics, and an updated netlist with tuned settings written in.
    """
    # Build evaluators if needed
    if get_S is None:
        if models is None:
            raise ValueError("Either provide get_S (and optionally get_Ss) or provide models for SAX evaluator.")
        get_S = make_sax_evaluator(netlist, models, port_list)
    if get_Ss is None:
        if wl_grid is None:
            wl_grid = np.array([1.55e-6], dtype=float)  # single point
        def _get_Ss(params: Dict[str, float]) -> List[np.ndarray]:
            return [get_S({**params, "wavelength": float(wl)}) for wl in wl_grid]
        get_Ss = _get_Ss

    # Parameter vector helpers
    lows = np.array([t.lo for t in tunables], dtype=float)
    highs = np.array([t.hi for t in tunables], dtype=float)
    x = read_params_from_netlist(netlist, tunables) if x0 is None else np.array(x0, dtype=float)
    x = np.minimum(np.maximum(x, lows), highs)

    def x_to_params(z: np.ndarray) -> Dict[str, float]:
        return {f"{t.inst}__{t.key}": float(v) for t, v in zip(tunables, z)}

    def loss(z: np.ndarray) -> float:
        p = x_to_params(z)
        J = 0.0
        if weights.get("deliver", 0.0) != 0.0:
            J += weights["deliver"] * objective_delivery(get_S, port_list, in_ports, out_ports, p, drive=drive)
        if weights.get("flat", 0.0) != 0.0:
            J += weights["flat"] * objective_flatness(get_Ss, port_list, in_ports, out_ports, p, drive=drive)
        if weights.get("reflect", 0.0) != 0.0:
            J += weights["reflect"] * objective_reflection(get_S, port_list, in_ports, p,
                                                           drive="single" if drive.startswith("single") else "single")
        return float(J)

    rng = np.random.default_rng(seed)
    best_x, best_val = x.copy(), float(loss(x))

    # SciPy -> Nelder-Mead ; else random search
    if _HAVE_SCIPY:
        for _ in range(n_restarts):
            x0r = np.minimum(np.maximum(x + 0.1*(rng.random(len(x))-0.5)*(highs-lows), lows), highs)
            res = minimize(lambda z: loss(np.minimum(np.maximum(z, lows), highs)),
                           x0r, method="Nelder-Mead",
                           options={"maxiter": maxiter, "xatol": 1e-5, "fatol": 1e-5, "disp": False})
            xr = np.minimum(np.maximum(res.x, lows), highs)
            val = loss(xr)
            if val < best_val:
                best_x, best_val = xr.copy(), float(val)
    else:
        for _ in range(max(2000, 300*len(x))):
            xr = lows + (highs - lows)*rng.random(len(x))
            val = loss(xr)
            if val < best_val:
                best_x, best_val = xr.copy(), float(val)

    # Final metrics at best_x (center wavelength)
    params = x_to_params(best_x)
    S0 = get_S({**params})
    T0 = submatrix(S0, port_list, in_ports, out_ports)
    if drive == "svd":
        delivered = svd_bound(T0)
    else:
        sel = drive.split(":", 1)[1]
        e = np.zeros((len(in_ports),), dtype=np.complex128)
        e[in_ports.index(sel)] = 1.0
        delivered = float(np.sum(np.abs(T0 @ e) ** 2))

    # Update netlist with optimized settings (instance-local keys)
    netlist_opt = write_params_to_netlist(netlist, tunables, best_x)

    return {
        "x_opt": best_x,
        "params_opt": params,
        "delivered_center": delivered,
        "insertion_loss_dB_center": db10_from_power(delivered),
        "netlist_optimized": netlist_opt,
    }