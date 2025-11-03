# demo_netlist.py

import gdsfactory as gf
import gplugins.sax as gs
import sax
import jax
import jax.numpy as jnp
import inspect


# -----------------------------
# 1) Layout: your QAM-8 modulator
# -----------------------------
@gf.cell
def qam8_modulator():
    c = gf.Component()

    # three MZMs
    mzm_bit1 = c << gf.components.mzis.mzm()
    mzm_bit2 = c << gf.components.mzis.mzm()
    mzm_bit3 = c << gf.components.mzis.mzm()

    # splitters / combiners
    splitter1 = c << gf.components.mmi1x2()
    splitter2 = c << gf.components.mmi1x2()
    combiner1 = c << gf.components.mmi1x2()
    combiner2 = c << gf.components.mmi1x2()

    # rotate combiners so ports face the right way
    combiner1.rotate(180)
    combiner2.rotate(180)

    # place components
    splitter1.move((-100, 180))
    splitter2.move((0, 300))

    mzm_bit1.move((100, 360))
    mzm_bit2.move((100, 240))
    mzm_bit3.move((100, 120))

    combiner1.move((460, 180))
    combiner2.move((560, 300))

    # route everything
    for p1, p2 in [
        (splitter1.ports["o2"], splitter2.ports["o1"]),
        (splitter1.ports["o3"], mzm_bit3.ports["o1"]),
        (splitter2.ports["o2"], mzm_bit1.ports["o1"]),
        (splitter2.ports["o3"], mzm_bit2.ports["o1"]),
        (mzm_bit1.ports["o2"], combiner2.ports["o3"]),
        (mzm_bit2.ports["o2"], combiner1.ports["o3"]),
        (mzm_bit3.ports["o2"], combiner1.ports["o2"]),
        (combiner1.ports["o1"], combiner2.ports["o2"]),
    ]:
        gf.routing.route_single(
            c,
            p1,
            p2,
            cross_section="strip",
            radius=5,
        )

    # expose I/O ports
    c.add_port("o1", port=splitter1.ports["o1"])
    c.add_port("o2", port=combiner2.ports["o1"])

    return c


# -----------------------------
# 2) Simple analytic MZI model
# -----------------------------
def analytic_mzi(*, wl=1.55, top_phi: float = 0.0, bot_phi: float = 0.0):
    """
    Very simple 2-port MZI-like model with ports (o1, o2).
    - transfer from o1->o2 is 0.5*(e^{j top_phi} + e^{j bot_phi})
    - reciprocal
    - no reflections
    - IMPORTANT: returns non-empty arrays even with no args, so SAX can dummy-build
    """
    t = 0.5 * (jnp.exp(1j * top_phi) + jnp.exp(1j * bot_phi))
    t = jnp.asarray([t])  # shape (1,)
    z = jnp.asarray([0.0 + 0.0j])
    return {
        ("o2", "o1"): t,
        ("o1", "o2"): t,
        ("o1", "o1"): z,
        ("o2", "o2"): z,
    }


# -----------------------------
# 3) Build GDSF → SAX netlist
# -----------------------------
qam8_cell = qam8_modulator()
qam8_raw = qam8_cell.get_netlist(exclude_port_types=("electrical",))

instances = qam8_raw["instances"].keys()

models = {}
for name in instances:
    if "bend_euler" in name:
        models[name] = gs.models.bend
    elif "straight" in name:
        models[name] = gs.models.straight
    elif "mmi1x2" in name or ("mmi" in name and "mmi1x2" not in models):
        models[name] = gs.models.mmi1x2
    elif "mzi" in name or "mzm" in name:
        models[name] = analytic_mzi  

qam8_net = sax.netlist(qam8_raw)

print("Instances in QAM8 netlist:", qam8_raw["instances"].keys())

# Map everything the netlist might produce
qam8_models = {
    "straight": gs.models.straight,
    "bend_euler": gs.models.bend,
    "mmi1x2": gs.models.mmi1x2,
    # the netlist said it needed "mzi", so map that:
    "mzi": analytic_mzi,
    # and in case it ever emits "mzm":
    "mzm": analytic_mzi,
}

# build the composite circuit
circ, info = sax.circuit(
    netlist=qam8_net,
    models=qam8_models,
    backend="forward",        # your sax supports this
    ignore_impossible_connections=True,
)


# -----------------------------
# 4) Helper: robust S-key finder
# -----------------------------
def _find_key(Sd, out_name, in_name):
    # exact match
    k = (out_name, in_name)
    if k in Sd:
        return k

    # suffix match
    cands = [
        kk
        for kk in Sd.keys()
        if kk[0].endswith(out_name) and kk[1].endswith(in_name)
    ]
    if cands:
        return sorted(cands)[0]

    # fallback
    if Sd:
        return next(iter(Sd.keys()))

    raise KeyError(
        f"Could not find S[{out_name},{in_name}] in keys={list(Sd.keys())}"
    )


# probe once to see real keys
Sd_probe = circ(wl=1.55)
print("Probe S-keys:", list(Sd_probe.keys()))


# -----------------------------
# 5) Find tunable params
# -----------------------------
all_args = list(inspect.signature(circ).parameters)
phi_params = [p for p in all_args if p != "wl" and p.endswith("_phi")]
print("Tunable phase params:", phi_params)


# -----------------------------
# 6) Objective (single-wl, because this SAX returns {} on vector wl)
# -----------------------------
def make_objective(circ, in_port="o1", out_port="o2", wls=None, param_names=()):
    # pick exactly ONE wl to keep backend happy
    if wls is None:
        wl0 = 1.55
    else:
        wl0 = float(wls[0])

    def obj(x):
        kwargs = {k: v for k, v in zip(param_names, x)}
        Sd = circ(wl=wl0, **kwargs)

        if not Sd:
            # backend returned empty dict -> worst possible loss
            return 1.0

        key = _find_key(Sd, out_port, in_port)
        t = jnp.asarray(Sd[key])
        return 1.0 - jnp.mean(jnp.abs(t) ** 2)

    return obj


# -----------------------------
# 7) Minimal Adam
# -----------------------------
def adam_minimize(fun, x0, steps=400, lr=0.05, b1=0.9, b2=0.999, eps=1e-8):
    val_and_grad = jax.value_and_grad(fun)
    m = jnp.zeros_like(x0)
    v = jnp.zeros_like(x0)
    x = x0

    for t in range(1, steps + 1):
        val, g = val_and_grad(x)
        m = b1 * m + (1.0 - b1) * g
        v = b2 * v + (1.0 - b2) * (g * g)
        mhat = m / (1.0 - b1**t)
        vhat = v / (1.0 - b2**t)
        x = x - lr * mhat / (jnp.sqrt(vhat) + eps)

    return x


# -----------------------------
# 8) Run optimization
# -----------------------------
wls = jnp.linspace(1.53, 1.57, 61)
objective = make_objective(
    circ,
    in_port="o1",
    out_port="o2",
    wls=wls,
    param_names=phi_params,
)

x0 = jnp.zeros((len(phi_params),), dtype=jnp.float64)
x_best = adam_minimize(objective, x0, steps=300, lr=0.05)

best_kwargs = {k: float(v) for k, v in zip(phi_params, x_best)}

# -----------------------------
# 9) Report IL across band (Python loop)
# -----------------------------
il_values = []
for wl in list(jnp.linspace(1.53, 1.57, 61)):
    Sd = circ(wl=float(wl), **best_kwargs)
    if not Sd:
        il_values.append(100.0)
        continue
    key = _find_key(Sd, "o2", "o1")
    t = jnp.asarray(Sd[key])
    power = jnp.abs(t) ** 2
    il_db = -10.0 * jnp.log10(jnp.maximum(power, 1e-15))
    il_values.append(float(il_db))

mean_il = sum(il_values) / len(il_values)

print("Mean IL over 1.53–1.57 um (dB):", mean_il)
print("Best params:", best_kwargs)
