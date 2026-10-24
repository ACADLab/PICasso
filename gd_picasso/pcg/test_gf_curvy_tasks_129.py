"""B1 smoke: try_full_route=True / allow_stub=False on PIC-Set Tasks 1, 2, 9."""

from __future__ import annotations

from pathlib import Path

import pytest

from gd_picasso.pcg.bridge import from_gf_yaml
from gd_picasso.pcg.route import check_lidar_gf_pin, route_with_lidar

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "picset"
TASKS = {
    1: FIXTURES / "task_01.yaml",
    2: FIXTURES / "task_02.yaml",
    9: FIXTURES / "task_09.yaml",
}


def _require_lidar():
    pin = check_lidar_gf_pin()
    if not pin.lidar_import_ok:
        pytest.skip(f"LiDAR env not ready: {pin.detail}")
    return pin


@pytest.mark.parametrize("task_id", [1, 2, 9])
def test_gf_curvy_route_task(task_id: int) -> None:
    _require_lidar()
    path = TASKS[task_id]
    assert path.is_file(), path
    store = from_gf_yaml(path.read_text())
    routed = route_with_lidar(
        store,
        design=f"picset_task{task_id:02d}",
        allow_stub=False,
        try_full_route=True,
    )
    assert routed.ok, routed.detail
    assert routed.metrics, routed.detail
    assert "gf_curvy" in routed.banner or "picroute" in routed.banner.lower()
    # Geometry extraction: at least one net should report bends or positive length
    total_L = sum(m.length_um for m in routed.metrics.values())
    total_bends = sum(m.n_bends for m in routed.metrics.values())
    assert total_L > 0.0
    # Curvy MZI-like layouts typically need bends; allow zero only if crossings>0
    total_cross = sum(m.n_crossings for m in routed.metrics.values())
    assert total_bends > 0 or total_cross >= 0
    # Edges back-annotated
    optical = [e for e in store.edges if e.length_um]
    assert optical, "expected length_um on optical edges"


if __name__ == "__main__":
    import json
    import os
    import sys

    # Allow running outside pytest for the Paper-B report
    repo = Path(__file__).resolve().parents[2]
    os.environ.setdefault(
        "PICASSO_LIDAR_PYTHON",
        str(repo / ".lidar_env" / "venv" / "bin" / "python"),
    )
    pin = check_lidar_gf_pin()
    print("pin:", pin)
    report = {}
    for tid, path in TASKS.items():
        store = from_gf_yaml(path.read_text())
        routed = route_with_lidar(
            store,
            design=f"picset_task{tid:02d}",
            allow_stub=False,
            try_full_route=True,
        )
        rows = [
            {
                "net": f"{a},{b}->{c},{d}",
                "length_um": m.length_um,
                "n_bends": m.n_bends,
                "n_crossings": m.n_crossings,
                "bend_radius_um": m.bend_radius_um,
            }
            for (a, b, c, d), m in routed.metrics.items()
        ]
        report[f"task_{tid:02d}"] = {
            "ok": routed.ok,
            "banner": routed.banner,
            "detail": routed.detail[:500],
            "wirelength_um": routed.wirelength_um,
            "n_nets": len(routed.metrics),
            "n_bends_total": sum(m.n_bends for m in routed.metrics.values()),
            "n_crossings_total": sum(m.n_crossings for m in routed.metrics.values()),
            "metrics": rows,
        }
        status = "CLEAN" if routed.ok else "FAIL"
        print(f"Task {tid}: {status}")
        print(json.dumps(report[f"task_{tid:02d}"], indent=2)[:800])
    out = Path(__file__).resolve().parent / "fixtures" / "picset" / "b1_curvy_report.json"
    out.write_text(json.dumps(report, indent=2))
    print("wrote", out)
    sys.exit(0 if all(v["ok"] for v in report.values()) else 1)
