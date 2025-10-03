# PICasso

What’s inside

schemas.py → JSON netlist schema (Pydantic)

placer.py → ensures instances get safe placements (diagonal fallback)

router.py → builds/routs designs deterministically with gdsfactory

pipeline.py → orchestrates LLM call → validated netlist → GDS

cli.py → command-line interface (run pipeline with a problem + JSON)

README.md → usage instructions and explanation

sample_problem.txt → demo problem description

sample_llm_netlist.json → demo LLM-like JSON netlist

How to use
pip install gdsfactory pydantic

# Run pipeline with the sample problem + netlist
python -m picasso_flow.cli \
  --problem sample_problem.txt \
  --llm-json sample_llm_netlist.json \
  --out-gds design.gds


Replace --llm-json with actual LLM outputs (JSON).

Extend run_pipeline() in pipeline.py to call your real LLM.

This way, the LLM only emits connectivity (JSON) while gdsfactory handles deterministic PnR/routing — avoiding the issues you saw.

Do you want me to also add a KLayout DRC auto-hook into this package, so it runs after every build?
