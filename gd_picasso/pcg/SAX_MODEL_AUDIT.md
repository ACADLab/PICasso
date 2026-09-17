# SAX model silent-default audit

Physically-null library defaults (e.g. `loss_dB_cm=0.0` on gplugins `straight`)
pass gate checks while producing meaningless FoMs. This table is the one-pass
audit of the SAX surface used by the PCG ΔIL harness.

Generated from `gd_picasso.pcg.sax_models.SAX_PARAM_AUDIT`.

| component | param | library default | what we set | source | risk |
|---|---|---|---|---|---|
| straight | loss_dB_cm | 0.0 | 0.7 | Table II / PIC-Set waveguide target | silent_null |
| bend_euler / bend_circular | loss | model-dependent / often 0 | use gs.models.bend (no override yet) | gplugins sax; needs PDK-calibrated bend loss | unknown |
| mmi1x2 / mmi2x2 | excess_loss | often ideal / 0 | library default (no override) | gplugins; excess loss not forced | silent_null |
| coupler | loss / coupling | ideal splitter common | library default | gplugins | unknown |
| straight_heater_metal | length / loss | generic_tech length often 10 µm; loss via straight stub | mapped to lossy straight (loss_dB_cm=0.7) | gate harness; Cornerstone default heater L≈320 µm — re-baseline open | silent_null |
| ring_single | S-model | compound / may fall back to bend | gs.models.ring_single if present else bend | gplugins hasattr fallback | stub |
| via_stack_heater_mtop | S-model | missing | lossy straight stub | electrical cell appearing in get_netlist() | stub |

## What the audit actually found

Besides the known `straight.loss_dB_cm=0.0`:

| finding | status |
|---|---|
| MMI excess loss often ideal/0 | **silent_null class** — not overridden yet |
| Heater `length` defaults (~10 µm generic_tech vs ~320 µm Cornerstone) | **silent_null class** — FoM scale error; re-baseline still open |
| Bend loss unspecified / often 0 | **unknown** — needs PDK numbers, not just a flag |
| `ring_single` → bend fallback | **stub** — wrong physics if hasattr fails |
| Via stacks mapped to lossy straight | **stub** — electrical cell in optical FoM |

Honest scope note: this pass was a *surface catalogue* of the models the gate already imports, not an automated signature crawl of all gplugins defaults. It did surface risk beyond `loss_dB_cm`, but the only *measured* silent-null we have forced to a non-zero value so far is waveguide loss. MMI/bend/heater still need the same treatment once numbers are chosen.
