# λλ locate pass — 2026-09-29 (Lane λλ/Env)

Goal: find a **working copy** of `unitary_inference.py` / `optical_compiler`
(with any PSD / embedding L929 patches) before vendoring SHA+patch.

## Searched (no working tree)

| Location | Result |
|---|---|
| Repo tree (`PICasso`, `files/`, `files-2/`, `gd_picasso/probes/`) | Absent — probes *import* λλ; never committed |
| Git history / dangling blobs (`git log -S`, `git grep`, `fsck`) | Only `psd_gate.py` import sites; no `unitary_inference.py` blob |
| Conda envs `picasso`, `gdiffps`, base (`/opt/homebrew/anaconda3`) | Not installed; no `.pth` / site-packages hit |
| uv `.venv` site-packages | Missing |
| `~/Desktop`, `~/Documents`, `~/Downloads` (maxdepth 6) | No `unitary_inference.py`, no `optical_compiler/` |
| `~/Library/Mobile Documents` (iCloud) | No hit |
| Cursor / Claude agent stores + transcripts | Sep 17 note claims prior “vendored standalone” session, but file not persisted; later same-day sessions report not on disk |
| Browser / shell history | No clone URL retained |
| Public GitHub name guesses (`cornell-*`, `racheesingh/*`, `lambda-lambda/*`, …) | Empty placeholder `github.com/lambda-lambda/lambda-lambda` (unrelated user); no Cornell artifact repo found |
| PyPI `unitary-inference` | 404 |
| `mdfind` / home-wide `find` for `unitary_inference.py` | Zero hits |

## Provenance note

Author message on 2026-09-17 described a private working session that:

- Vendored `unitary_inference.py` standalone (no Gurobi / mesh ILP)
- Wrote `psd_gate.py` for Algorithm-1 (`I−AA† ⪰ 0`) omitted upstream
- Closed spec→SAX to ~1e-13 with Cornerstone heaters

That working copy was **never committed** and is **not recoverable** from this
host. Upstream Cornell λλ appears **unpublished** (no LICENSE / public SHA
available from this locate pass). Author permission was already flagged as a
release blocker.

## Blockers to SHA+patch vendor

1. No upstream SHA to pin.
2. No `embedding.py` to regenerate an L929 patch against.
3. Cannot invent / re-implement upstream under the lane policy.

## Unblocked without λλ (this commit)

- `cspdk==1.3.2` pin + install (gf remains 9.23.0)
- Cornerstone re-measure → FINDINGS header
- PSD **matrix** reject regression via `psd_numpy` (Algorithm-1 math)
- CS vertical slice `||T−αU|| ~ 1e-13` recovered under 1.3.2 (SAX half)

Spec-parse PSD reject + math probes (`lower.py`, `picset_specs.py`, …) stay
blocked until a working λλ tree is supplied.
