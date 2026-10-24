"""SiEPIC EBeam port map and Euler-bend routing rule (ubcpdk 3.3.2)."""

from gd_picasso.backends.siepic import (
    EULER_BEND_RMIN_UM,
    PORT_WIDTH_UM,
    STRIP_WIDTH_UM,
    UBC_STRIP_RADIUS_MIN_UM,
    UBC_TECH_RADIUS_UM,
    euler_bend_settings,
    port_width_um,
)


def test_strip_is_500nm_and_euler_rmin_is_15um() -> None:
    assert STRIP_WIDTH_UM == 0.5
    assert UBC_TECH_RADIUS_UM == 10.0
    assert UBC_STRIP_RADIUS_MIN_UM == 5.0
    assert EULER_BEND_RMIN_UM == 15.0
    assert euler_bend_settings()["radius"] == 15.0


def test_450nm_cells_differ_from_generic_500nm() -> None:
    assert port_width_um("ebeam_y_adiabatic", "o1") == 0.45
    assert port_width_um("ebeam_DC_te895", "o1") == 0.45
    assert PORT_WIDTH_UM["straight"]["o1"] == 0.5
    assert PORT_WIDTH_UM["ebeam_bdc_te1550"]["o1"] == 0.5
