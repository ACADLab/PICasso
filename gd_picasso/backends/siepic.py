"""SiEPIC EBeam backend (ubcpdk).

Port names and widths are the optical ports of ``ubcpdk==3.3.2``
default cells (``cells.<name>()``), not generic_tech assumptions.
Strip waveguides at 1550 nm use ``TECH.wg_width`` (0.5 µm), the same
500 nm as generic_tech / Cornerstone strip. Cells whose ports are not
0.5 µm are listed in ``WIDTHS_NOT_500NM`` — including 0.45 µm ports on
``ebeam_y_adiabatic`` and the te895 family. ``add_tapers`` inserts a
linear taper when a 0.5 µm port is wired to one of those.

Euler bends: ubcpdk ``TECH.radius`` is 10 µm and the strip cross-section
``radius_min`` is 5 µm. This backend requires ``R_min = 15`` µm.
"""

from __future__ import annotations

from typing import Dict, List

import ubcpdk
from ubcpdk.tech import TECH, strip
from ubcpdk.tech import route_single as ubc_route_single

UBCPDK_VERSION = "3.3.2"
WAVELENGTH_NM = 1550
STRIP_MODEL = "ebeam_wg_integral_1550"
# Live library value. ubcpdk 3.3.2 Tech.wg_width is 0.5 µm.
STRIP_WIDTH_UM = float(TECH.wg_width)
GENERIC_TECH_STRIP_WIDTH_UM = 0.5
# Published ubcpdk defaults (not the routing rule below).
UBC_TECH_RADIUS_UM = float(TECH.radius)
UBC_STRIP_RADIUS_MIN_UM = float(strip().radius_min)
# Required Euler-bend radius for this backend.
EULER_BEND_RMIN_UM = 15.0
GAP_STRIP_UM = float(TECH.gap_strip)

if ubcpdk.__version__ != UBCPDK_VERSION:
    raise ImportError(
        f"siepic port map is frozen for ubcpdk=={UBCPDK_VERSION}, "
        f"found {ubcpdk.__version__}"
    )
if STRIP_WIDTH_UM != GENERIC_TECH_STRIP_WIDTH_UM:
    raise ImportError(
        f"ubcpdk TECH.wg_width={STRIP_WIDTH_UM} µm, expected 0.5"
    )

# component -> optical port names, in ubcpdk cell port order
COMPONENT_PORT_MAP: Dict[str, List[str]] = {
    'ANT_MMI_1x2_te1550_3dB_BB': ['o1', 'o3', 'o2'],
    'GC_SiN_TE_1310_8degOxide_BB': ['o1'],
    'GC_SiN_TE_1550_8degOxide_BB': ['o1'],
    'GC_TE_1310_8degOxide_BB': ['o1'],
    'GC_TE_1550_8degOxide_BB': ['o1'],
    'GC_TM_1310_8degOxide_BB': ['o1'],
    'GC_TM_1550_8degOxide_BB': ['o1'],
    'add_fiber_array': ['o2', 'o1'],
    'add_fiber_array_pads_rf': ['o1', 'o2'],
    'add_pads': ['o1', 'o2'],
    'add_pads_rf': ['o1', 'o2'],
    'bend_euler': ['o1', 'o2'],
    'bend_s': ['o1', 'o2'],
    'coupler': ['o1', 'o2', 'o3', 'o4'],
    'coupler_ring': ['o1', 'o2', 'o3', 'o4'],
    'crossing_SiN_1550': ['o1', 'o2', 'o3', 'o4'],
    'crossing_SiN_1550_extended': ['o2', 'o3', 'o4', 'o1'],
    'crossing_horizontal': ['o2', 'o3', 'o4', 'o1'],
    'crossing_manhattan': ['o1', 'o2', 'o3', 'o4'],
    'ebeam_DC_2m1_te895': ['o1', 'o4', 'o2', 'o3'],
    'ebeam_DC_te895': ['o1', 'o4', 'o2', 'o3'],
    'ebeam_MMI_2x2_5050_te1310': ['o2', 'o1', 'o3', 'o4'],
    'ebeam_Polarizer_TM_1550_UQAM': ['o1', 'o2'],
    'ebeam_YBranch_895': ['o2', 'o3', 'o1'],
    'ebeam_YBranch_te1310': ['o2', 'o3', 'o1'],
    'ebeam_adiabatic_te1550': ['o2', 'o1', 'o3', 'o4'],
    'ebeam_adiabatic_tm1550': ['o1', 'o2', 'o3', 'o4'],
    'ebeam_bdc_te1550': ['o1', 'o2', 'o3', 'o4'],
    'ebeam_bdc_tm1550': ['o2', 'o1', 'o3', 'o4'],
    'ebeam_crossing4': ['o1', 'o3', 'o4', 'o2'],
    'ebeam_dream_FAVE_SiN_1310_BB': ['o1'],
    'ebeam_dream_FAVE_SiN_1550_BB': ['o1'],
    'ebeam_dream_FAVE_Si_1310_BB': ['o1'],
    'ebeam_dream_FAVE_Si_1550_BB': ['o1'],
    'ebeam_dream_FaML_SiN_1550_BB': ['o1'],
    'ebeam_dream_FaML_Si_1310_BB': ['o1'],
    'ebeam_dream_FaML_Si_1550_BB': ['o1'],
    'ebeam_dream_splitter_1x2_te1550_BB': ['o2', 'o3', 'o1'],
    'ebeam_gc_te1310': ['o1'],
    'ebeam_gc_te1310_broadband': ['o1'],
    'ebeam_gc_te1550': ['o1'],
    'ebeam_gc_te1550_90nmSlab': ['o1'],
    'ebeam_gc_te1550_broadband': ['o1'],
    'ebeam_gc_te895': ['o1'],
    'ebeam_gc_tm1550': ['o1'],
    'ebeam_routing_taper_te1550_w500nm_to_w3000nm_L20um': ['o1', 'o2'],
    'ebeam_routing_taper_te1550_w500nm_to_w3000nm_L40um': ['o1', 'o2'],
    'ebeam_sin_dream_splitter1x2_te1550_BB': ['o3', 'o2', 'o1'],
    'ebeam_splitter_adiabatic_swg_te1550': ['o1', 'o3', 'o2', 'o4'],
    'ebeam_splitter_swg_assist_te1310': ['o4', 'o3', 'o1', 'o2'],
    'ebeam_splitter_swg_assist_te1310_ANT': ['o4', 'o3', 'o1', 'o2'],
    'ebeam_splitter_swg_assist_te1550': ['o4', 'o2', 'o1', 'o3'],
    'ebeam_splitter_swg_assist_te1550_ANT': ['o2', 'o1', 'o3', 'o4'],
    'ebeam_swg_edgecoupler': ['o1'],
    'ebeam_terminator_SiN_1310': ['o1'],
    'ebeam_terminator_SiN_1550': ['o1'],
    'ebeam_terminator_SiN_te895': ['o1'],
    'ebeam_terminator_te1310': ['o1'],
    'ebeam_terminator_te1550': ['o1'],
    'ebeam_terminator_tm1550': ['o1'],
    'ebeam_y_1310': ['o2', 'o3', 'o1'],
    'ebeam_y_1550': ['o1', 'o2', 'o3'],
    'ebeam_y_adiabatic': ['o1', 'o2', 'o3'],
    'ebeam_y_adiabatic_1310': ['o2', 'o3', 'o1'],
    'ebeam_y_adiabatic_500pin': ['o1', 'o2', 'o3'],
    'grating_coupler_elliptical': ['o1'],
    'mmi1x2': ['o1', 'o2', 'o3'],
    'mmi2x2': ['o1', 'o2', 'o3', 'o4'],
    'mzi': ['o1', 'o2', 'o4', 'o3'],
    'mzi_1x1': ['o1', 'o2'],
    'mzi_heater': ['o1', 'o2'],
    'mzi_heater_2x2': ['o1', 'o2', 'o4', 'o3'],
    'pack_doe': ['0_o1', '0_o2'],
    'pack_doe_grid': ['0_o1', '0_o2'],
    'photonic_wirebond_surfacetaper_1310': ['o1'],
    'photonic_wirebond_surfacetaper_1550': ['o1'],
    'ring_double': ['o1', 'o2', 'o3', 'o4'],
    'ring_double_heater': ['o1', 'o2', 'o3', 'o4'],
    'ring_single': ['o2', 'o1'],
    'ring_single_heater': ['o1', 'o2'],
    'siepic_o_gc_te1270_BB': ['o1'],
    'siepic_o_pwbstlas_si_BB': ['o1'],
    'spiral': ['o1', 'o2'],
    'spiral_racetrack': ['o1', 'o2'],
    'spiral_racetrack_heater': ['o1', 'o2'],
    'straight': ['o1', 'o2'],
    'straight_heater_meander': ['o1', 'o2'],
    'straight_heater_metal': ['o1', 'o2'],
    'taper': ['o1', 'o2'],
    'taper_SiN_750_3000': ['o1', 'o2'],
    'taper_si_simm_1310': ['o2', 'o1'],
    'taper_si_simm_1550': ['o2', 'o1'],
    'thermal_phase_shifter_multimode_': ['o1', 'o2'],
    'thermal_phase_shifter_te_1310_': ['o1', 'o2'],
    'thermal_phase_shifter_te_1310_50': ['o1', 'o2'],
    'thermal_phase_shifter_te_1550_50': ['o2', 'o1'],
}

# component -> optical port -> width in µm (ubcpdk 3.3.2 defaults)
PORT_WIDTH_UM: Dict[str, Dict[str, float]] = {
    'ANT_MMI_1x2_te1550_3dB_BB': {'o1': 0.75, 'o3': 0.75, 'o2': 0.75},
    'GC_SiN_TE_1310_8degOxide_BB': {'o1': 0.75},
    'GC_SiN_TE_1550_8degOxide_BB': {'o1': 0.75},
    'GC_TE_1310_8degOxide_BB': {'o1': 0.35},
    'GC_TE_1550_8degOxide_BB': {'o1': 0.5},
    'GC_TM_1310_8degOxide_BB': {'o1': 0.35},
    'GC_TM_1550_8degOxide_BB': {'o1': 0.5},
    'add_fiber_array': {'o2': 0.5, 'o1': 0.5},
    'add_fiber_array_pads_rf': {'o1': 0.5, 'o2': 0.5},
    'add_pads': {'o1': 0.5, 'o2': 0.5},
    'add_pads_rf': {'o1': 0.5, 'o2': 0.5},
    'bend_euler': {'o1': 0.5, 'o2': 0.5},
    'bend_s': {'o1': 0.5, 'o2': 0.5},
    'coupler': {'o1': 0.5, 'o2': 0.5, 'o3': 0.5, 'o4': 0.5},
    'coupler_ring': {'o1': 0.5, 'o2': 0.5, 'o3': 0.5, 'o4': 0.5},
    'crossing_SiN_1550': {'o1': 0.75, 'o2': 0.75, 'o3': 0.75, 'o4': 0.75},
    'crossing_SiN_1550_extended': {'o2': 0.75, 'o3': 0.75, 'o4': 0.75, 'o1': 0.75},
    'crossing_horizontal': {'o2': 0.75, 'o3': 0.75, 'o4': 0.75, 'o1': 0.75},
    'crossing_manhattan': {'o1': 0.75, 'o2': 0.75, 'o3': 0.75, 'o4': 0.75},
    'ebeam_DC_2m1_te895': {'o1': 0.45, 'o4': 0.45, 'o2': 0.45, 'o3': 0.45},
    'ebeam_DC_te895': {'o1': 0.45, 'o4': 0.45, 'o2': 0.45, 'o3': 0.45},
    'ebeam_MMI_2x2_5050_te1310': {'o2': 0.8, 'o1': 0.8, 'o3': 0.8, 'o4': 0.8},
    'ebeam_Polarizer_TM_1550_UQAM': {'o1': 1.04, 'o2': 0.924},
    'ebeam_YBranch_895': {'o2': 0.45, 'o3': 0.45, 'o1': 0.45},
    'ebeam_YBranch_te1310': {'o2': 0.8, 'o3': 0.8, 'o1': 0.8},
    'ebeam_adiabatic_te1550': {'o2': 0.5, 'o1': 0.5, 'o3': 0.5, 'o4': 0.5},
    'ebeam_adiabatic_tm1550': {'o1': 0.5, 'o2': 0.5, 'o3': 0.5, 'o4': 0.5},
    'ebeam_bdc_te1550': {'o1': 0.5, 'o2': 0.5, 'o3': 0.5, 'o4': 0.5},
    'ebeam_bdc_tm1550': {'o2': 0.5, 'o1': 0.5, 'o3': 0.5, 'o4': 0.5},
    'ebeam_crossing4': {'o1': 0.5, 'o3': 0.5, 'o4': 0.5, 'o2': 0.5},
    'ebeam_dream_FAVE_SiN_1310_BB': {'o1': 0.75},
    'ebeam_dream_FAVE_SiN_1550_BB': {'o1': 0.75},
    'ebeam_dream_FAVE_Si_1310_BB': {'o1': 0.75},
    'ebeam_dream_FAVE_Si_1550_BB': {'o1': 0.75},
    'ebeam_dream_FaML_SiN_1550_BB': {'o1': 0.75},
    'ebeam_dream_FaML_Si_1310_BB': {'o1': 0.35},
    'ebeam_dream_FaML_Si_1550_BB': {'o1': 0.5},
    'ebeam_dream_splitter_1x2_te1550_BB': {'o2': 0.5, 'o3': 0.5, 'o1': 0.5},
    'ebeam_gc_te1310': {'o1': 0.35},
    'ebeam_gc_te1310_broadband': {'o1': 0.35},
    'ebeam_gc_te1550': {'o1': 0.5},
    'ebeam_gc_te1550_90nmSlab': {'o1': 0.5},
    'ebeam_gc_te1550_broadband': {'o1': 0.5},
    'ebeam_gc_te895': {'o1': 0.45},
    'ebeam_gc_tm1550': {'o1': 0.5},
    'ebeam_routing_taper_te1550_w500nm_to_w3000nm_L20um': {'o1': 0.5, 'o2': 3.0},
    'ebeam_routing_taper_te1550_w500nm_to_w3000nm_L40um': {'o1': 0.5, 'o2': 3.0},
    'ebeam_sin_dream_splitter1x2_te1550_BB': {'o3': 0.8, 'o2': 0.8, 'o1': 0.8},
    'ebeam_splitter_adiabatic_swg_te1550': {'o1': 0.5, 'o3': 0.5, 'o2': 0.5, 'o4': 0.5},
    'ebeam_splitter_swg_assist_te1310': {'o4': 0.35, 'o3': 0.35, 'o1': 0.35, 'o2': 0.35},
    'ebeam_splitter_swg_assist_te1310_ANT': {'o4': 0.35, 'o3': 0.35, 'o1': 0.35, 'o2': 0.35},
    'ebeam_splitter_swg_assist_te1550': {'o4': 0.5, 'o2': 0.5, 'o1': 0.5, 'o3': 0.5},
    'ebeam_splitter_swg_assist_te1550_ANT': {'o2': 0.5, 'o1': 0.5, 'o3': 0.5, 'o4': 0.5},
    'ebeam_swg_edgecoupler': {'o1': 0.5},
    'ebeam_terminator_SiN_1310': {'o1': 0.8},
    'ebeam_terminator_SiN_1550': {'o1': 0.75},
    'ebeam_terminator_SiN_te895': {'o1': 0.45},
    'ebeam_terminator_te1310': {'o1': 0.35},
    'ebeam_terminator_te1550': {'o1': 0.5},
    'ebeam_terminator_tm1550': {'o1': 0.5},
    'ebeam_y_1310': {'o2': 0.35, 'o3': 0.35, 'o1': 0.35},
    'ebeam_y_1550': {'o1': 0.5, 'o2': 0.5, 'o3': 0.5},
    'ebeam_y_adiabatic': {'o1': 0.45, 'o2': 0.45, 'o3': 0.45},
    'ebeam_y_adiabatic_1310': {'o2': 0.35, 'o3': 0.35, 'o1': 0.35},
    'ebeam_y_adiabatic_500pin': {'o1': 0.5, 'o2': 0.5, 'o3': 0.5},
    'grating_coupler_elliptical': {'o1': 0.5},
    'mmi1x2': {'o1': 0.5, 'o2': 0.5, 'o3': 0.5},
    'mmi2x2': {'o1': 0.5, 'o2': 0.5, 'o3': 0.5, 'o4': 0.5},
    'mzi': {'o1': 0.5, 'o2': 0.5, 'o4': 0.5, 'o3': 0.5},
    'mzi_1x1': {'o1': 0.5, 'o2': 0.5},
    'mzi_heater': {'o1': 0.5, 'o2': 0.5},
    'mzi_heater_2x2': {'o1': 0.5, 'o2': 0.5, 'o4': 0.5, 'o3': 0.5},
    'pack_doe': {'0_o1': 0.5, '0_o2': 0.5},
    'pack_doe_grid': {'0_o1': 0.5, '0_o2': 0.5},
    'photonic_wirebond_surfacetaper_1310': {'o1': 0.35},
    'photonic_wirebond_surfacetaper_1550': {'o1': 0.5},
    'ring_double': {'o1': 0.5, 'o2': 0.5, 'o3': 0.5, 'o4': 0.5},
    'ring_double_heater': {'o1': 0.5, 'o2': 0.5, 'o3': 0.5, 'o4': 0.5},
    'ring_single': {'o2': 0.5, 'o1': 0.5},
    'ring_single_heater': {'o1': 0.5, 'o2': 0.5},
    'siepic_o_gc_te1270_BB': {'o1': 0.35},
    'siepic_o_pwbstlas_si_BB': {'o1': 0.41},
    'spiral': {'o1': 0.5, 'o2': 0.5},
    'spiral_racetrack': {'o1': 0.5, 'o2': 0.5},
    'spiral_racetrack_heater': {'o1': 0.5, 'o2': 0.5},
    'straight': {'o1': 0.5, 'o2': 0.5},
    'straight_heater_meander': {'o1': 0.5, 'o2': 0.5},
    'straight_heater_metal': {'o1': 0.5, 'o2': 0.5},
    'taper': {'o1': 0.5, 'o2': 0.5},
    'taper_SiN_750_3000': {'o1': 0.75, 'o2': 3.0},
    'taper_si_simm_1310': {'o2': 3.0, 'o1': 0.35},
    'taper_si_simm_1550': {'o2': 3.0, 'o1': 0.5},
    'thermal_phase_shifter_multimode_': {'o1': 3.0, 'o2': 3.0},
    'thermal_phase_shifter_te_1310_': {'o1': 0.35, 'o2': 0.35},
    'thermal_phase_shifter_te_1310_50': {'o1': 0.35, 'o2': 0.35},
    'thermal_phase_shifter_te_1550_50': {'o2': 0.5, 'o1': 0.5},
}

WIDTHS_NOT_500NM: Dict[str, Dict[str, float]] = {
    name: dict(ports)
    for name, ports in PORT_WIDTH_UM.items()
    if any(abs(w - GENERIC_TECH_STRIP_WIDTH_UM) > 1e-9 for w in ports.values())
}


def port_width_um(component: str, port: str) -> float:
    """Optical port width in µm for a ubcpdk 3.3.2 default cell."""
    try:
        return PORT_WIDTH_UM[component][port]
    except KeyError as exc:
        raise KeyError(f"{component}.{port} is not an optical SiEPIC port") from exc


def euler_bend_settings() -> Dict[str, object]:
    """Settings that keep Euler bends at ``EULER_BEND_RMIN_UM``."""
    return {
        "component": "bend_euler",
        "radius": EULER_BEND_RMIN_UM,
        "cross_section": "strip",
        "allow_min_radius_violation": False,
    }


def route_single(*args, **kwargs):
    """ubcpdk strip route with Euler radius forced to 15 µm."""
    kwargs.setdefault("bend", "bend_euler")
    kwargs.setdefault("radius", EULER_BEND_RMIN_UM)
    kwargs.setdefault("cross_section", "strip")
    return ubc_route_single(*args, **kwargs)

