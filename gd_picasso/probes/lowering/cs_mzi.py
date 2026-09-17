"""Cornerstone MZI: mmi2x2 -> heater on one arm -> mmi2x2.
Extract its 2x2 transfer matrix from SAX and fit (theta, phi) against a target.
"""
import numpy as np, jax
jax.config.update("jax_enable_x64", True)
import sax
from cspdk.si220.cband import models as M, PDK
PDK.activate()

LOSS_DB_CM = 0.7            # PICasso Table II strip loss, NOT the 0.0/3.0 defaults
ARM_L      = 320.0          # Cornerstone straight_heater_metal default length (um)

netlist = {
    "instances": {
        "c1":  {"component": "mmi2x2"},
        "psT": {"component": "straight_heater_metal"},
        "psB": {"component": "straight_heater_metal"},
        "c2":  {"component": "mmi2x2"},
    },
    "connections": {
        "psT,o1": "c1,o3", "psB,o1": "c1,o4",
        "c2,o1":  "psT,o2", "c2,o2": "psB,o2",
    },
    "ports": {"in1": "c1,o1", "in2": "c1,o2", "out1": "c2,o3", "out2": "c2,o4"},
}

circuit, _ = sax.circuit(netlist=netlist, models=M.get_models())

def T(vT, vB, wl=1.55):
    s = circuit(wl=wl,
        psT={"voltage": vT, "length": ARM_L, "loss_dB_cm": LOSS_DB_CM},
        psB={"voltage": vB, "length": ARM_L, "loss_dB_cm": LOSS_DB_CM})
    sd = sax.sdict(s)
    return np.array([[complex(sd[(i,o)]) for i in ("in1","in2")]
                     for o in ("out1","out2")])

if __name__ == "__main__":
    for vT, vB in [(0,0), (1,0), (0.5,0), (2,0)]:
        M2 = T(vT, vB)
        amp = np.linalg.norm(M2[:,0])
        print(f"vT={vT:>4} vB={vB:>4}  |T| col-norm={amp:.5f}  "
              f"IL={-20*np.log10(amp):.3f} dB   split={abs(M2[0,0])**2/amp**2:.4f}/"
              f"{abs(M2[1,0])**2/amp**2:.4f}")
    print()
    M2 = T(0,0); print("T(0,0) =\n", np.round(M2,5))
    print("\nnormalized (unitary part):\n", np.round(M2/np.linalg.norm(M2[:,0]),5))
