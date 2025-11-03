# demo_gf_mzi_optimize.py
import numpy as np
import gdsfactory as gf
from gf_optimize import SaxCircuit, NetlistOptimizer
from typing import Dict

# ---- 1) Build a small MZI in GDSFactory (geometry for netlist only)
c1 = gf.components.coupler90()      # 4 optical ports (o1..o4)
c2 = gf.components.coupler90()
wg_u = gf.components.straight(length=200.0)  # um (just to have unique refs)
wg_l = gf.components.straight(length=220.0)

top = gf.Component("mzi_demo")
r1 = top << c1
r2 = top << c2
ru = top << wg_u
rl = top << wg_l

# (Place/route omitted for brevity; for netlist-only we can connect by port names)

# Top-level IO ports (left side = inputs; right side = outputs)
top.add_port(name="in0", center=r1.ports["o1"].center, layer=r1.ports["o1"].layer, orientation=180)
top.add_port(name="in1", center=r1.ports["o2"].center, layer=r1.ports["o2"].layer, orientation=180)
top.add_port(name="out0", center=r2.ports["o3"].center, layer=r2.ports["o3"].layer, orientation=0)
top.add_port(name="out1", center=r2.ports["o4"].center, layer=r2.ports["o4"].layer, orientation=0)

# NOTE: For real designs, you'd connect with routes and extract a physical netlist.
# For SAX, we only need a logical netlist (instances + connections).
netlist = {
    "instances": {
        "c1": {"component": "coupler90"},
        "c2": {"component": "coupler90"},
        "wg_u": {"component": "waveguide"},
        "wg_l": {"component": "waveguide"},
    },
    "connections": [
        ("c1", "o3", "wg_u", "o1"),
        ("wg_u", "o2", "c2", "o1"),
        ("c1", "o4", "wg_l", "o1"),
        ("wg_l", "o2", "c2", "o2"),
    ],
    "ports": {
        "in0": ("c1", "o1"),
        "in1": ("c1", "o2"),
        "out0": ("c2", "o3"),
        "out1": ("c2", "o4"),
    },
}

# ---- 2) SAX primitive models (very lightweight)
# Each returns an S-dictionary keyed as "p1,p2" with complex amplitudes or uses sdense later.
def model_coupler90(params):
    wl = params["wavelength"]
    kappa = params.get("kappa", 1/np.sqrt(2))          # ~3 dB
    a = params.get("cpl_amp", 0.995)                   # excess loss factor
    t = a * np.sqrt(1 - kappa**2)
    k = 1j * a * kappa

    # port order for coupler90: (o1,o2,o3,o4). We'll label "1,2,3,4".
    S = {
        ("1","3"): t, ("1","4"): k,
        ("2","3"): k, ("2","4"): t,
        ("3","1"): t, ("4","1"): k,
        ("3","2"): k, ("4","2"): t,
    }
    return {"ports": ["1","2","3","4"], "S": S}

def model_waveguide(params):
    wl = params["wavelength"]
    neff = params.get("neff", 2.4)
    alpha_dB_per_cm = params.get("alpha_dB_per_cm", 2.0)
    L_um = params.get("length_um", 200.0)
    phi_extra = params.get("phi", 0.0)                 # tunable phase
    L_m = L_um * 1e-6
    beta = 2*np.pi*neff / wl
    amp = 10**(-alpha_dB_per_cm * (L_m*100) / 20.0)    # field loss
    e = amp * np.exp(1j*(beta*L_m + phi_extra))
    # 2-port: pass-through with phase; no reflection
    return {"ports": ["1","2"], "S": {("1","2"): e, ("2","1"): e}}

# Map instances to models + per-instance param mappers
models = {
    "coupler90": model_coupler90,
    "waveguide": model_waveguide,
}

# Build a SAX circuit function from the logical netlist
def build_sax_circuit(nl, models):
    import sax
    # Wrap models to SAX's expected callable interface
    sax_models = {}
    for name, fn in models.items():
        def make_closure(f):
            def wrapped(**kwargs):
                Sd = f(kwargs)           # {"ports": [...], "S": {("i","j"): val}}
                return sax.sdict(Sd["S"], ports=Sd["ports"])
            return wrapped
        sax_models[name] = make_closure(fn)

    circ = sax.circuit(netlist=nl, models=sax_models)

    # Top-level port order (consistent naming)
    port_list = list(nl["ports"].keys())

    def circuit_fn(params: dict):
        return circ(**params)

    return SaxCircuit(circuit_fn=circuit_fn, port_list=port_list)

sax_circ = build_sax_circuit(netlist, models)

# ---- 3) Define tunable params and wavelength grid
# We tune only the *extra phase* on the two arms: phi_u, phi_l
param_names = ["phi_u", "phi_l"]

# We propagate these into the waveguide instances via fixed_params, using SAX parameter naming:
# We’ll rely on our model_waveguide() reading "phi" and "length_um" etc. per instance,
# so we set per-instance overrides below using SAX's instance scoping:
#   "<inst>__<param_name>" convention is common; adjust if your SAX version differs.
fixed_params = {
    # WG lengths (geometry)
    "wg_u__length_um": 200.0,
    "wg_l__length_um": 220.0,

    # Couplers
    "c1__kappa": 1/np.sqrt(2),
    "c2__kappa": 1/np.sqrt(2),
    "c1__cpl_amp": 0.995,
    "c2__cpl_amp": 0.995,

    # Loss and neff
    "wg_u__neff": 2.4, "wg_l__neff": 2.4,
    "wg_u__alpha_dB_per_cm": 2.0, "wg_l__alpha_dB_per_cm": 2.0,
}

# Translate generic params -> instance-scoped params for the evaluator
def params_adapter(generic: Dict[str, float]) -> Dict[str, float]:
    p = dict(fixed_params)
    p["wg_u__phi"] = float(generic["phi_u"])
    p["wg_l__phi"] = float(generic["phi_l"])
    return p

# Patch SaxCircuit to insert adapter
orig_S_dense = sax_circ.S_dense
def S_dense_with_adapter(user_params: Dict[str, float]):
    p = params_adapter(user_params)
    return orig_S_dense(p)
sax_circ.S_dense = S_dense_with_adapter

# Wavelength grid
wl0 = 1.55e-6
wls = np.linspace(1.545e-6, 1.555e-6, 31)

# ---- 4) Optimize for multiple metrics
from gf_optimize import NetlistOptimizer

# A) Maximize delivery to out1 (with SVD drive over inputs ["in0", "in1"])
optA = NetlistOptimizer(
    sax_circuit=sax_circ,
    in_ports=["in0", "in1"],
    out_ports=["out1"],
    wl_grid=wls,
    param_names=param_names,
    bounds={"phi_u": (-np.pi, np.pi), "phi_l": (-np.pi, np.pi)},
    fixed_params={},   # not used (we adapted above)
)

x0 = np.array([0.0, np.pi/2])  # start from a deliberately bad relative phase
resA = optA.optimize(x0=x0,
                     weights={"deliver": 1.0, "reflect": 0.0, "flat": 0.0},
                     drive="svd",
                     maxiter=400, n_restarts=8, seed=42)

print("\n=== Optimize: Max delivery to out1 (center wl) ===")
print("phi_u, phi_l = ", resA["x_opt"])
print("achieved_center =", resA["achieved_center"], "(IL dB:", resA["insertion_loss_dB_center"], ")")
print("svd_bound_center =", resA["sigma2_center"])

# B) Add band flatness penalty (robust across wavelength)
resB = optA.optimize(x0=resA["x_opt"],
                     weights={"deliver": 1.0, "reflect": 0.0, "flat": 0.05},
                     drive="svd",
                     maxiter=400, n_restarts=6, seed=7)
print("\n=== Optimize: Delivery + Flatness (band) ===")
print("phi_u, phi_l = ", resB["x_opt"])
print("achieved_center =", resB["achieved_center"], "(IL dB:", resB["insertion_loss_dB_center"], ")")
print("svd_bound_center =", resB["sigma2_center"])

# C) If you care about reflection at a single driven port, switch to single-port drive:
#    in_ports=["in0"]; drive="single:in0"; include a reflection weight.
optC = NetlistOptimizer(
    sax_circuit=sax_circ,
    in_ports=["in0"],
    out_ports=["out1"],
    wl_grid=wls,
    param_names=param_names,
    bounds={"phi_u": (-np.pi, np.pi), "phi_l": (-np.pi, np.pi)},
)
resC = optC.optimize(x0=x0,
                     weights={"deliver": 1.0, "reflect": 0.02, "flat": 0.0},
                     drive="single:in0",
                     maxiter=400, n_restarts=8, seed=1)
print("\n=== Optimize: Single-port drive + reflection penalty ===")
print("phi_u, phi_l = ", resC["x_opt"])
print("achieved_center =", resC["achieved_center"], "(IL dB:", resC["insertion_loss_dB_center"], ")")
print("svd_bound_center =", resC["sigma2_center"])