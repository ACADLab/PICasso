"""
Unit tests for LVS validator.

Under gdsfactory 9.23, ``gdsfactory.utils.lvs`` is missing (soft-break).
Real layout-vs-schematic cases importorskip until a real LVS backend returns.
"""

from __future__ import annotations

import pytest

from gd_picasso.validators.lvs_validator import LVS_AVAILABLE, LVSValidator


def test_lvs_soft_skip_when_gf9_helper_missing() -> None:
    """Without gdsfactory.utils.lvs, validator must soft-skip — not fake LVS."""
    if LVS_AVAILABLE:
        pytest.skip("gdsfactory.utils.lvs is present; soft-skip path N/A")

    validator = LVSValidator(enabled=True)
    assert validator.enabled is False

    import gdsfactory as gf

    passed, report = validator.validate(gf.components.mmi1x2())
    assert passed is True  # skipped, not a fabricated match claim
    assert report.get("lvs_skipped_gf9") is True
    assert any("soft-skip" in w.lower() or "missing" in w.lower() for w in report["warnings"])
    assert report["errors"] == []


@pytest.mark.skipif(not LVS_AVAILABLE, reason="gdsfactory.utils.lvs missing (gf 9 soft-break)")
def test_layout_matches_schematic() -> None:
    """Matching layout/schematic — requires real gf LVS helper."""
    pytest.importorskip("gdsfactory.utils.lvs")
    import gdsfactory as gf

    validator = LVSValidator(enabled=True)
    layout = gf.components.mmi1x2()
    schematic = gf.components.mmi1x2()
    passed, report = validator.validate(layout, schematic)
    assert passed is True
    assert report.get("matched") is True


@pytest.mark.skipif(not LVS_AVAILABLE, reason="gdsfactory.utils.lvs missing (gf 9 soft-break)")
def test_missing_instances_fails() -> None:
    pytest.importorskip("gdsfactory.utils.lvs")
    pytest.skip("Needs a controlled schematic/layout mismatch fixture once LVS returns")


@pytest.mark.skipif(not LVS_AVAILABLE, reason="gdsfactory.utils.lvs missing (gf 9 soft-break)")
def test_port_mismatch_fails() -> None:
    pytest.importorskip("gdsfactory.utils.lvs")
    pytest.skip("Needs a controlled schematic/layout mismatch fixture once LVS returns")
