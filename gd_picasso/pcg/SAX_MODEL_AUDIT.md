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

## Open correctness debt

1. **Heater re-baseline** against `cspdk.si220.cband` (Cornerstone L≈320 µm) — still open.
2. Bend / MMI excess-loss overrides once PDK numbers are chosen.
3. Ring S-model: prefer expanded coupler+loop over black-box fallback.

Use `build_lossy_models()` for any FoM path; call `ensure_jax_x64()` at import (done in `gd_picasso` / `gd_picasso.pcg`).
