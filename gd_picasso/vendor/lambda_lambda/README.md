# λλ (`unitary_inference`) vendor — Lane λλ/Env

**Status (2026-09-29): working tree NOT FOUND on this machine.**

Policy (plan Must-fix §2): vendor as **upstream SHA + explicit patch file**,
never a fresh bare SHA. Do **not** invent upstream sources.

## Required upstream pieces

- `unitary_inference.py` — `parse_spec_sympy_eval`, `infer_unitary_from_spec`,
  `clements_decomposition`
- `optical_compiler/ast.py` (and whatever that package imports)
- Preserve Algorithm-1 PSD fix (lives in-repo as
  [`gd_picasso/probes/lowering/psd_gate.py`](../../probes/lowering/psd_gate.py))
- Preserve any `embedding.py` ~L929 workaround as
  `patches/0002-embedding-L929.patch` once the upstream file is available

## Drop-in procedure (when a working copy appears)

1. Record upstream remote + commit SHA in `UPSTREAM_SHA.txt` (one line: full SHA).
2. Copy the minimal tree under `src/` (or symlink) so
   `PYTHONPATH=gd_picasso/vendor/lambda_lambda/src` imports `unitary_inference`.
3. Export patches against that SHA into `patches/`:
   - `0001-…` only if PSD must live *inside* upstream; otherwise keep
     `psd_gate.py` as the in-front wrapper (preferred — already committed).
   - `0002-embedding-L929.patch` if that workaround is still required.
4. Apply patches in order; run
   `pytest gd_picasso/probes/lowering/tests/test_psd_reject.py -q`
   and the math probes (`recon_check`, `lower`, `picset_specs`).

## What is already in-repo without λλ

| Artifact | Role |
|---|---|
| `probes/lowering/psd_gate.py` | Algorithm-1 PSD wrapper (needs λλ to parse specs) |
| `probes/lowering/psd_numpy.py` | Matrix-form PSD reject (no λλ) — regression covered |
| Cornerstone probes + FINDINGS | Re-measured under `cspdk==1.3.2` + gf 9.23.0 |

See `SEARCH_LOG.md` for the locate pass.
