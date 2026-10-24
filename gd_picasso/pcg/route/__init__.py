"""PCG route package — LiDAR wrap + min-plus kernels."""

from __future__ import annotations

from .lidar_wrap import (
    LIDAR_GF_PIN,
    PICASSO_GF_PIN,
    LidarPinReport,
    LidarRouteResult,
    check_lidar_gf_pin,
    fidelity_vs_routed,
    route_with_lidar,
)
from .minplus import (
    ROUTER_CUT_LINE,
    MinPlusResult,
    min_plus_relax,
    route_point_to_point,
    soft_approaches_hard,
    soft_min_plus_relax,
)

__all__ = [
    "LIDAR_GF_PIN",
    "PICASSO_GF_PIN",
    "LidarPinReport",
    "LidarRouteResult",
    "check_lidar_gf_pin",
    "fidelity_vs_routed",
    "route_with_lidar",
    "ROUTER_CUT_LINE",
    "MinPlusResult",
    "min_plus_relax",
    "route_point_to_point",
    "soft_approaches_hard",
    "soft_min_plus_relax",
]
