"""Full 2-mode Cornerstone circuit: in-phase -> MZI -> out-phases.
Fit (vphi, vT, va, vb) so that T_sim = alpha * U_target.
"""
import numpy as np, jax
jax.config.update("jax_enable_x64", True)
import sax
from scipy.optimize import least_squares
from cspdk.si220.cband import models as M, PDK
PDK.activate()

LOSS, L = 0.7, 320.0
PS = lambda: {"component": "straight_heater_metal"}

netlist = {
 "instances": {"pin":PS(), "pbal":PS(), "c1":{"component":"mmi2x2"}, "psT":PS(), "psB":PS(),
               "c2":{"component":"mmi2x2"}, "pa":PS(), "pb":PS()},
 "connections": {"c1,o2":"pin,o2", "c1,o1":"pbal,o2",
                 "psT,o1":"c1,o3", "psB,o1":"c1,o4",
                 "c2,o1":"psT,o2", "c2,o2":"psB,o2",
                 "pa,o1":"c2,o3", "pb,o1":"c2,o4"},
 "ports": {"in1":"pbal,o1", "in2":"pin,o1", "out1":"pa,o2", "out2":"pb,o2"},
}
circuit,_ = sax.circuit(netlist=netlist, models=M.get_models())
K = dict(length=L, loss_dB_cm=LOSS)

def T(v):
    vphi, vT_, va, vb = v
    s = sax.sdict(circuit(wl=1.55,
        pin={"voltage":vphi, **K}, pbal={"voltage":0.0, **K}, psT={"voltage":vT_, **K}, psB={"voltage":0.0, **K},
        pa={"voltage":va, **K},  pb={"voltage":vb, **K}))
    return np.array([[complex(s[(i,o)]) for i in ("in1","in2")] for o in ("out1","out2")])

def fit(U):
    def res(v):
        A = T(v); a = np.linalg.norm(A[:,0])/np.linalg.norm(U[:,0])
        d = (A - a*U).ravel(); return np.concatenate([d.real, d.imag])
    best=None
    for s in range(30):
        rng=np.random.default_rng(s)
        r=least_squares(res, rng.uniform(0,2,4), xtol=1e-14, ftol=1e-14)
        if best is None or r.cost<best.cost: best=r
    return best

TARGETS = {
 "Hadamard": np.array([[1,1],[1,-1]],dtype=complex)/np.sqrt(2),
 "cross":    np.array([[0,1],[1,0]],dtype=complex),
 "bar":      np.eye(2,dtype=complex),
 "AllReduce":np.array([[1,1],[1,-1]],dtype=complex)/np.sqrt(2),
}
print(f"{'target':10s} {'vphi':>7} {'vTheta':>7} {'va':>7} {'vb':>7} {'IL dB':>7} {'||T-aU||':>10}")
print("-"*60)
for name,U in TARGETS.items():
    r=fit(U); A=T(r.x); a=np.linalg.norm(A[:,0])/np.linalg.norm(U[:,0])
    print(f"{name:10s} {r.x[0]:7.4f} {r.x[1]:7.4f} {r.x[2]:7.4f} {r.x[3]:7.4f} "
          f"{-20*np.log10(a):7.3f} {np.linalg.norm(A-a*U):10.2e}")
