# Patches against vendored λλ upstream SHA

Empty until `../UPSTREAM_SHA.txt` is a real commit.

Intended patch series:

1. **PSD Algorithm-1** — prefer keeping
   `gd_picasso/probes/lowering/psd_gate.py` as an *external* guard in front of
   `infer_unitary_from_spec` (already committed). Only add
   `0001-psd-feasibility.patch` if upstream must be modified in-tree.
2. **`embedding.py` ~L929 workaround** — `0002-embedding-L929.patch` once the
   upstream file is available and the workaround is still required.

Do not vendor a bare SHA without these patches / the external PSD guard.
