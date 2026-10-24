# λλ (`unitary_inference`) vendor — Lane λλ/Env

**Status (2026-09-30): VENDORED** from
[vaibhavmehta1/LambdaLambda](https://github.com/vaibhavmehta1/LambdaLambda)
`main` @ `08d1a215aa48966d34334216acc6bfa38b7fe74f` (no LICENSE — research
vendor only).

Policy: vendor as **upstream SHA + explicit patch file**, never a fresh bare
SHA. PSD guard stays in-repo as `psd_gate.py` (preferred over patching
upstream inference).

## Layout

| Path | Role |
|---|---|
| `UPSTREAM_SHA.txt` | Full commit SHA + source URL |
| `src/unitary_inference.py` | `parse_spec_sympy_eval`, `infer_unitary_from_spec`, `clements_decomposition` |
| `src/symbolic_executor.py` | Spec interpreter helper |
| `src/optical_compiler/` | Full package (`ast`, `embedding`, …) |
| `patches/0002-embedding-L929.patch` | Restores corrupted `src_neighbor == dst_neighbor` |

## Import wire

```bash
# Explicit
PYTHONPATH=gd_picasso/vendor/lambda_lambda/src python -c "import unitary_inference"

# Automatic for repo tests / probe package import
# — conftest.py, [tool.pytest.ini_options] pythonpath, and
#   gd_picasso.probes.lowering._path_bootstrap
```

## Acceptance

```bash
pytest gd_picasso/probes/lowering/tests/test_psd_reject.py -q
python -m gd_picasso.probes.lowering.test_formal_acceptance_stubs
```

Pass: `import unitary_inference`; PSD reject (numpy + λλ spec path);
MZI 2×2 rebuild residual &lt; 1e-12 (1e-13 slice stub).

## What stays outside the vendor

| Artifact | Role |
|---|---|
| `probes/lowering/psd_gate.py` | Algorithm-1 PSD wrapper (needs λλ to parse specs) |
| `probes/lowering/psd_numpy.py` | Matrix-form PSD reject (no λλ) |

No Gurobi required for inference / PSD / Clements probes.
