#!/usr/bin/env python3
"""
run_pnr_and_drc.py
------------------
Performs placement & routing from a GDSFactory-style YAML netlist (or from a PhIDO circuit DSL),
writes a GDS, and optionally runs a KLayout DRC to catch routing overlaps/spacing violations.

Usage:
  python run_pnr_and_drc.py --netlist path/to/gf_netlist.yaml --out gds/out.gds
  python run_pnr_and_drc.py --circuit-dsl path/to/circuit_dsl.yaml --out gds/out.gds

Notes:
- If you pass --circuit-dsl, we convert it to a GDSFactory netlist using PhotonicsAI.Photon.utils.dsl_to_gf.
- Overlap avoidance: gdsfactory's autorouter generates collision-free waveguide paths for the
  links specified under `routes: optical: links:`. We then run a DRC script to verify.
"""

import argparse
import sys
from pathlib import Path
import yaml

# Import gdsfactory. It must be installed in your environment.
import gdsfactory as gf

# Try to import PhIDO helpers if available (for circuit_dsl -> gf netlist)
try:
    from PhotonicsAI.Photon import DemoPDK
    from PhotonicsAI.Photon import utils as ph_utils
    HAVE_PHIDO = True
except Exception:
    HAVE_PHIDO = False

# Optional: KLayout DRC runner from this repo
try:
    # This module shells out to KLayout using a .drc script
    from PhotonicsAI.Photon.drc.drc import run_drc as run_klayout_drc
    HAVE_KLAYOUT = True
except Exception:
    HAVE_KLAYOUT = False


def load_gf_netlist(path: Path) -> dict:
    """Loads a GDSFactory netlist YAML file into a Python dict."""
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data


def ensure_placements(netlist: dict) -> dict:
    """Guarantee there is a 'placements' block. If missing, place instances on a simple diagonal grid.
    GDSFactory requires placements to build a layout from YAML.
    """
    if "instances" not in netlist:
        raise ValueError("Netlist must contain an 'instances' dictionary.")
    if "placements" in netlist and netlist["placements"]:
        return netlist

    placements = {}
    x = y = 0.0
    step = 50.0
    for name in netlist["instances"]:
        placements[name] = {"x": float(x), "y": float(y), "rotation": 0}
        x += step
        y += step * 0.5
    netlist["placements"] = placements
    return netlist


def build_gds_from_gf_netlist(netlist: dict, out_gds: Path) -> gf.Component:
    """Create a gdsfactory Component from a GF YAML netlist and write it to disk.
    This triggers autorouting for routes specified under routes: optical: links:.
    """
    # gdsfactory expects a YAML string, so dump dict to YAML then parse
    yaml_text = yaml.dump(netlist, default_flow_style=False, sort_keys=False)
    c = gf.read.from_yaml(yaml_text)
    # Write GDS
    out_gds.parent.mkdir(parents=True, exist_ok=True)
    c.write_gds(str(out_gds))
    return c


def main():
    parser = argparse.ArgumentParser(description="Place & route photonic circuits and check overlap DRC.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--netlist", type=str, help="Path to GDSFactory netlist YAML.")
    group.add_argument("--circuit-dsl", type=str, help="Path to PhIDO circuit_dsl YAML (will be converted).")

    parser.add_argument("--out", type=str, required=True, help="Output GDS file path.")
    parser.add_argument("--skip-drc", action="store_true", help="Skip KLayout DRC even if available.")
    args = parser.parse_args()

    out_gds = Path(args.out)

    if args.circuit_dsl:
        if not HAVE_PHIDO:
            print("ERROR: --circuit-dsl was provided but PhotonicsAI modules are not importable.", file=sys.stderr)
            sys.exit(2)
        # Load circuit_dsl YAML and convert to gf netlist using repo utils
        with open(args.circuit_dsl, "r") as f:
            circuit_dsl = yaml.safe_load(f)

        # circuit_dsl may be top-level keyed; accept either direct dict or wrapped
        if "nodes" not in circuit_dsl and isinstance(circuit_dsl, dict) and len(circuit_dsl) == 1:
            # unwrap first key
            circuit_dsl = list(circuit_dsl.values())[0]

        gf_netlist = ph_utils.dsl_to_gf(circuit_dsl)
        gf_netlist = ensure_placements(gf_netlist)
        comp = build_gds_from_gf_netlist(gf_netlist, out_gds)

    else:
        gf_netlist = load_gf_netlist(Path(args.netlist))
        gf_netlist = ensure_placements(gf_netlist)
        comp = build_gds_from_gf_netlist(gf_netlist, out_gds)

    print(f"Wrote GDS at: {out_gds}")

    # Optionally run KLayout DRC to catch overlaps (requires KLayout and repo's drc script)
    if not args.skip_drc and HAVE_KLAYOUT:
        try:
            # Run DRC using the repo's default script
            run_klayout_drc(str(out_gds), out_gds.stem)
        except Exception as e:
            print(f"Warning: DRC run failed: {e}", file=sys.stderr)
    else:
        if not HAVE_KLAYOUT:
            print("DRC skipped: PhotonicsAI.Photon.drc not available. Install KLayout or run your own DRC.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
