# Pre-registration amendment 2 (`n1-confirm-v2`)

Frozen before R1 finishes. Does **not** restart the in-flight R1 campaign
(arms A/B/C on tag `n1-confirm-v1` / commit `88265eb`). B_parity and the
functional oracle run **after** that campaign ends.

Source request: round-2 addendum (R0.6–R0.8, R7). No separate
`agent_addendum_round2b.md` file was present in the repo; this document is
the frozen copy of that request.

## R0.6 Prompt-parity arm

Arm id: `B_parity_yaml_exact_critic`.

- Output: gdsfactory YAML (same repair loop and ExactCritic + TaskContract feedback as Arm B).
- System prompt: `gd_picasso/agents/n1_arm_b_parity_prompt.py`.
- Same legal-port table, degree ≤ 1, connected graph, exported dangling ports, bend radius ≥ 5, and the 1×4 splitter tree as Arm C.
- Few-shot is the same tree written as YAML (`instances` / `connections` / `ports`), not JSON ops.
- User text includes the same “ignore exact instance-count” instruction as Arm C (`B_PARITY_IGNORE_INSTANCE_COUNT`). Default chosen: **include it**.
- Original Arm B is unchanged and stays in R1 for continuity.
- B_parity is **not** in the default arm tuple. Post-R1 command:

```bash
python -m gd_picasso.pcg.run_n1_campaign --campaign --picbench48 \
  --arms B_parity_yaml_exact_critic \
  --out-dir gd_picasso/pcg/n1_runs/dac27_confirm_b_parity
```

Hard stop: if B_parity uniform pass on tasks 1–46 is **≥** Arm C, report immediately and do not rerun.

Payload sidecar (does not change prompts, scoring, or call order): each future sample also appends `n1_payloads.jsonl` with `raw_response`, `final_yaml` (arms A/B/B_parity), and `final_json` (arm C). The scoring jsonl and CSV omit those fields. The in-flight R1 process imported the pre-sidecar module and will not write this file.

## R0.7 Held-out functional oracle

Module: `gd_picasso/pcg/functional_oracle.py`. Not imported by the repair loop.

SAX models added in `sax_models.build_lossy_models` (ideal, not foundry data):

- `mzi`: two 50/50 couplers and differential phase. `phi=0` cross (o1→o3, o2→o4); `phi=pi` bar (o1→o4, o2→o3).
- `crossing`: bar through-paths o1↔o3 and o2↔o4, zero crosstalk.

Applicable tasks (frozen; no others):

| Kind | Task ids | Pass rule |
|---|---|---|
| Equal split | **26, 30, 34** | Each output within **0.5 dB** of ideal `1/N`. Row sum of `|S|^2` ≤ `1+1e-3`. |
| Mesh permutation | **11, 13, 15, 17, 20, 21, 37, 38** | At the store’s stored heater phases (missing phase = 0), `|S|^2` is a permutation: claimed entry ≥ **0.5**, every other entry in that row ≤ **0.1**, row sums ≤ `1+1e-3`. Not all-to-all. |

Golden gate: oracle must pass every applicable golden fixture **before** it grades model outputs. If any applicable golden fails, stop (hard stop) and do not grade campaigns.

`functional_pass` is reported with Wilson 95% CI and a 2×2 table (uniform pass × functional pass) per arm. Round-1 stores are graded only if the raw stores were saved (they were not in the round-1 CSV).

Time box: 1.5 days from this tag. If goldens are not validated by then, stop and report.

## R0.8 Contract granularity

Post-hoc only. For every `min_nodes` failure in round 1 and in R1, recompute with MZI-equivalent counting: one `mzi` instance counts as **4** nodes (MMI + two arms + MMI). Report `pass_uniform_mzi_eq` beside `pass_uniform`. Also report fail counts per contract field (`min_nodes`, `min_io_ports`, `required_component_types`, `min_phase_shifters`) per arm.

## R7 PhIDO testbench (after R1)

Do not run PhIDO. Fetch its public 102-prompt testbench. Run Arm C (and B_parity if spend allows) on Levels 1–3, 5 samples. Map success to ExactCritic, GDS via `place_route_emit_gds`, DRC clean, and `route_ok`. Place PhIDO published pass@1/pass@5 beside ours and note definitional differences. List prompts whose components are outside our library. Time box 1 day, spend ≤ $15. Total spend hard stop remains **$60**.

## Hard stops (added)

- Functional oracle fails any applicable golden fixture: stop, do not grade campaigns.
- B_parity uniform pass on tasks 1–46 is ≥ Arm C: report immediately, do not rerun.

## Execution order after this tag

1. Let in-flight R1 (A/B/C @ `88265eb`) finish. Do not restart it.
2. Run B_parity alone on this tag.
3. Implement SAX execution of `functional_check` if still returning `functional_pass=None`, validate on the 46 goldens (applicable subset), then grade R1 and B_parity.
4. R0.8 tables, then R7.
