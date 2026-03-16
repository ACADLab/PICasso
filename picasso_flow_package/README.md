
# PICasso Flow (LLM → Netlist → Clean GDS)

This minimal flow consumes an **LLM-produced netlist** (JSON) and guarantees a **clean layout build** via gdsfactory with:
- **Placement legalization** (diagonal fallback)
- **Deterministic autorouting** (single-route per link; extend to bundles as needed)
- **Zero unconnected top ports** precondition (heuristic check hook)
- **GDS export**

> Intent: avoid PnR / routing chaos by forcing a validated netlist + controlled routing rather than letting the LLM freehand geometry.

## Install
```bash
pip install gdsfactory pydantic
```

## JSON Netlist Schema (expected)
```jsonc
{
  "instances": {
    "mzi": {"component": "mzi", "settings": {}, "x": 0, "y": 0, "rotation": 0},
    "gc0": {"component": "grating_coupler_te", "x": 50, "y": 25}
  },
  "connections": [
    ["gc0", "o0", "mzi", "o1"],
    ["mzi", "o2", "gc1", "o0"]
  ],
  "ports": {
    "in":  "gc0,o0",
    "out": "gc1,o0"
  },
  "models": {}
}
```

## Run (with a saved LLM JSON)
```bash
python -m picasso_flow.cli --problem problem.txt --llm-json llm_netlist.json --out-gds design.gds
```

## Extending to your LLM
Import `run_pipeline()` and pass your own `llm_call(prompt:str)->str` to return the JSON netlist string.

## Why this avoids routing issues
- The LLM **does not** draw geometry; it only emits **connectivity**.
- gdsfactory does **deterministic** routing (`get_route`) per connection, reducing crossings and enforcing bend radii.
- You can replace routing with `gf.routing.get_bundle` for multi-fiber links and `all_angle` routers if needed.
