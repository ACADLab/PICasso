"""Headless klayout_drc smoke tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from gd_picasso.pcg.klayout_drc import (
    R_MIN_CORNERSTONE_UM,
    R_MIN_SIEPIC_UM,
    r_min_for_pdk,
    run_drc,
)

VERIFY_GDS = (
    Path(__file__).resolve().parent / "n1_runs" / "layout_verify" / "task_01.gds"
)


def test_r_min_pdk_floors() -> None:
    assert r_min_for_pdk("cornerstone") == R_MIN_CORNERSTONE_UM
    assert r_min_for_pdk("siepic") == R_MIN_SIEPIC_UM


@pytest.mark.skipif(not VERIFY_GDS.is_file(), reason="run --verify first")
def test_run_drc_on_task01_gds() -> None:
    result = run_drc(VERIFY_GDS, task_id=1, route_bend_radii_um=[10.0])
    assert result.task_id == 1
    assert result.backend.startswith("klayout") or "shapely" in result.backend
    # No self-intersection / bend-floor hits on the representative MZI.
    kinds = {v.kind for v in result.violations}
    assert "self_intersection" not in kinds
    assert "bend_radius" not in kinds
    assert isinstance(result.drc_clean, bool)
    assert result.violation_count == len(result.violations)
