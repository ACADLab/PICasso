"""
Pure-PyTorch differentiable analytical transfer-matrix FoM for MZI arms.

Avoids the JAX/SAX autograd wall: arm lengths from (x, y) feed a 2×2
transfer-matrix model with the same physical constants as ``objective.py``:

    neff = 2.34
    wavelength_um = 1.55
    loss_dB_per_cm = 0.7   # Cornerstone FINDINGS / CS MZI IL bookkeeping

Also provides ``overlap_loss``: soft AABB repulsion with orientation-aware
port emission margins so LiDAR has runway for an Euler bend.

Claim discipline: this is an analytical FoM bridge for placement — not a
foundry SAX model and not CS_MODEL_SAX measurement.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .objective import NEFF, WAVELENGTH_UM, ObjectiveWeights
from .tensors import PlacementProblem, port_world

if TYPE_CHECKING:
    import torch

# Cornerstone FINDINGS (cspdk 1.3.2): waveguide propagation loss used in CS MZI IL.
LOSS_DB_PER_CM = 0.7

# Ideal 50:50 MMI field factor (lossless splitter/combiner half).
_MMI_FIELD = 1.0 / math.sqrt(2.0)

# Outward exclusion along each optical port so the router can start an Euler bend.
PORT_EMISSION_MARGIN_UM: float = 20.0
# softplus temperature (µm): smaller → closer to hard ReLU overlap.
OVERLAP_SOFTPLUS_BETA: float = 2.0
# Discrete horizontal routing-channel pitch for parallel MZI / mesh arms.
Y_CHANNEL_PITCH_UM: float = 25.0
# Minimum horizontal runway between consecutive topological mesh stages so
# LiDAR can fan out 4.0 µm separation bundles on dense butterfly permutations.
X_STAGE_GAP_UM: float = 150.0

# Components that define mesh "columns" (ignore heaters / straights / tapers
# when collapsing multi-hop MZI interiors into a single stage hop).
_STAGE_ANCHOR_PREFIXES: Tuple[str, ...] = (
    "mmi",
    "coupler",
    "crossing",
    "ebeam_y",
    "ebeam_Y",
    "ebeam_DC",
    "ANT_MMI",
)

# Explicit mesh-column name patterns (preferred over pure topo longest-path).
# Crossbar uses sw{row}_{col}_*; Beneš/Spanke use bn{stage}_* / sb{stage}_*.
_STAGE_NAME_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"^sw\d+_(\d+)_", re.I),          # crossbar column
    re.compile(r"^bn(\d+)_", re.I),               # Beneš stage
    re.compile(r"^sb(\d+)_", re.I),               # Spanke/Beneš-like
    re.compile(r"^wdm_mux(\d+)_", re.I),          # cascaded WDM mux stages
    re.compile(r"^lat(\d+)_", re.I),              # cascaded MZI lattice
    re.compile(r"^mzi(\d+)_", re.I),              # Clements / Reck cell index
    re.compile(r"^stage(\d+)_", re.I),
    re.compile(r"^col(\d+)_", re.I),
)


def _have_torch() -> bool:
    try:
        import torch  # noqa: F401

        return True
    except Exception:
        return False


def arm_length_torch(
    xy: "torch.Tensor",
    problem: PlacementProblem,
    arm_net_indices: Sequence[int],
    *,
    theta: Optional[np.ndarray] = None,
) -> "torch.Tensor":
    """Differentiable Manhattan arm length from trainable ``xy``."""
    import torch

    th = problem.theta_rad if theta is None else theta
    id_to_idx = problem.node_index()
    L = xy.new_zeros(())
    for ni in arm_net_indices:
        net = problem.nets[ni]
        i_s = id_to_idx[net.src.node_id]
        i_d = id_to_idx[net.dst.node_id]
        p_s_np, _ = port_world(problem, net.src, xy=problem.xy, theta=th)
        p_d_np, _ = port_world(problem, net.dst, xy=problem.xy, theta=th)
        off_s = p_s_np - problem.xy[i_s]
        off_d = p_d_np - problem.xy[i_d]
        p_s = xy[i_s] + xy.new_tensor(off_s)
        p_d = xy[i_d] + xy.new_tensor(off_d)
        delta = p_d - p_s
        L = L + torch.abs(delta[0]) + torch.abs(delta[1])
    return L


def waveguide_field_ri(
    length_um: "torch.Tensor",
    *,
    neff: float = NEFF,
    wavelength_um: float = WAVELENGTH_UM,
    loss_dB_per_cm: float = LOSS_DB_PER_CM,
) -> Tuple["torch.Tensor", "torch.Tensor"]:
    """Real/imag field transfer of a waveguide: a·(cos βL, -sin βL).

    Kept real-valued so ``torch.autograd`` can differentiate the FoM scalar.
    """
    import torch

    L_cm = length_um * 1e-4
    atten_db = loss_dB_per_cm * L_cm
    amp = torch.exp(-atten_db * (math.log(10.0) / 20.0))
    beta = 2.0 * math.pi * neff / wavelength_um
    phase = beta * length_um
    return amp * torch.cos(phase), -amp * torch.sin(phase)


def mzi_power(
    L_upper: "torch.Tensor",
    L_lower: "torch.Tensor",
    *,
    neff: float = NEFF,
    wavelength_um: float = WAVELENGTH_UM,
    loss_dB_per_cm: float = LOSS_DB_PER_CM,
    mmi_excess_loss_dB: float = 0.3,
) -> Tuple["torch.Tensor", "torch.Tensor"]:
    """Bar / cross optical power from arm lengths (real autograd path).

    Splitter/combiner: ideal 50:50 with Bᵢ convention
    ``(1/√2)·[[1, i], [i, 1]]``, plus optional MMI excess loss (FINDINGS 0.3 dB).
    """
    import torch

    u_r, u_i = waveguide_field_ri(
        L_upper, neff=neff, wavelength_um=wavelength_um, loss_dB_per_cm=loss_dB_per_cm
    )
    l_r, l_i = waveguide_field_ri(
        L_lower, neff=neff, wavelength_um=wavelength_um, loss_dB_per_cm=loss_dB_per_cm
    )
    mmi_amp = 10.0 ** (-mmi_excess_loss_dB / 20.0)
    s = _MMI_FIELD * mmi_amp

    # split: upper ← s·in, lower ← i·s·in  → then guide, then combine
    # arm fields after splitter:
    arm_u_r, arm_u_i = s * u_r, s * u_i
    # i * (l_r + i l_i) = -l_i + i l_r, times s
    arm_l_r, arm_l_i = s * (-l_i), s * l_r

    # combiner: out_bar = s*arm_u + i*s*arm_l ; out_cross = i*s*arm_u + s*arm_l
    i_arm_l_r, i_arm_l_i = -arm_l_i, arm_l_r
    i_arm_u_r, i_arm_u_i = -arm_u_i, arm_u_r
    bar_r = s * arm_u_r + s * i_arm_l_r
    bar_i = s * arm_u_i + s * i_arm_l_i
    cross_r = s * i_arm_u_r + s * arm_l_r
    cross_i = s * i_arm_u_i + s * arm_l_i

    p_bar = bar_r * bar_r + bar_i * bar_i
    p_cross = cross_r * cross_r + cross_i * cross_i
    return p_bar, p_cross


def extinction_and_il(
    p_bar: "torch.Tensor",
    p_cross: "torch.Tensor",
) -> Tuple["torch.Tensor", "torch.Tensor"]:
    """Return (ER_dB, IL_dB) with ER = P_bar/P_cross (clamped)."""
    import torch

    eps = p_bar.new_tensor(1e-18)
    er_db = 10.0 * torch.log10((p_bar + eps) / (p_cross + eps))
    il_db = -10.0 * torch.log10(p_bar + p_cross + eps)
    return er_db, il_db


def F_torch(
    xy: "torch.Tensor",
    problem: PlacementProblem,
    weights: Optional[ObjectiveWeights] = None,
    *,
    loss_dB_per_cm: float = LOSS_DB_PER_CM,
    wavelengths_um: Optional[Sequence[float]] = None,
) -> "torch.Tensor":
    """Differentiable spectral/extinction FoM to *minimize*.

    For each two-arm phase group, evaluate ER / IL on a small wavelength
    grid around ``weights.wavelength_um``. FoM accumulates:

        Σ_g [ IL_dB - ER_dB ]_mean_λ   (prefer high extinction, low IL)

    Gradients flow from this scalar into ``xy`` via arm-length Manhattan.
    """
    import torch

    w = weights or ObjectiveWeights()
    neff = float(w.neff)
    wl0 = float(w.wavelength_um)
    wls = list(wavelengths_um) if wavelengths_um is not None else [
        wl0 - 0.01,
        wl0,
        wl0 + 0.01,
    ]

    F = xy.new_zeros(())
    n_groups = 0
    for g in problem.phase_groups:
        if len(g.arm_net_indices) < 2:
            continue
        L_u = arm_length_torch(xy, problem, g.arm_net_indices[0])
        L_l = arm_length_torch(xy, problem, g.arm_net_indices[1])
        # Optional extra arms: fold into mean length of upper/lower only
        group_F = xy.new_zeros(())
        for wl in wls:
            p_bar, p_cross = mzi_power(
                L_u,
                L_l,
                neff=neff,
                wavelength_um=float(wl),
                loss_dB_per_cm=loss_dB_per_cm,
            )
            er_db, il_db = extinction_and_il(p_bar, p_cross)
            group_F = group_F + (il_db - er_db)
        F = F + group_F / float(len(wls))
        n_groups += 1

    if n_groups == 0:
        # No interferometer groups — soft zero that still connects to xy
        # via a tiny length regularizer so autograd graph stays valid.
        return (xy * 0.0).sum()
    return F


def _port_emission_extras(
    problem: PlacementProblem,
    *,
    margin_um: float = PORT_EMISSION_MARGIN_UM,
) -> np.ndarray:
    """Per-node (extra_hx, extra_hy) from outward optical-port runways.

    For each port orientation unit vector ``u``, grow the AABB along that
    axis by ``margin_um · |u_axis|`` (max over ports on each signed face,
    then sum opposite faces so both sides keep a bend runway).
    """
    n = problem.n_nodes
    # [neg_x, pos_x, neg_y, pos_y] extras per node
    faces = np.zeros((n, 4), dtype=np.float64)
    seen: Dict[int, set] = {i: set() for i in range(n)}

    def _consume(pref) -> None:
        i = int(pref.node_idx)
        key = (pref.port, round(float(pref.local_orient_rad), 6))
        if key in seen[i]:
            return
        seen[i].add(key)
        _, u = port_world(problem, pref, xy=problem.xy, theta=problem.theta_rad)
        ux, uy = float(u[0]), float(u[1])
        if ux < 0.0:
            faces[i, 0] = max(faces[i, 0], -ux * margin_um)
        elif ux > 0.0:
            faces[i, 1] = max(faces[i, 1], ux * margin_um)
        if uy < 0.0:
            faces[i, 2] = max(faces[i, 2], -uy * margin_um)
        elif uy > 0.0:
            faces[i, 3] = max(faces[i, 3], uy * margin_um)

    for net in problem.nets:
        _consume(net.src)
        _consume(net.dst)

    extras = np.zeros((n, 2), dtype=np.float64)
    extras[:, 0] = faces[:, 0] + faces[:, 1]
    extras[:, 1] = faces[:, 2] + faces[:, 3]
    return extras


def expanded_half_extents(
    problem: PlacementProblem,
    *,
    margin_um: float = PORT_EMISSION_MARGIN_UM,
) -> np.ndarray:
    """Footprint half-extents plus orientation-aware port emission margins."""
    return problem.half_extents + _port_emission_extras(problem, margin_um=margin_um)


def overlap_loss(
    xy: "torch.Tensor",
    problem: PlacementProblem,
    *,
    margin_um: float = PORT_EMISSION_MARGIN_UM,
    beta: float = OVERLAP_SOFTPLUS_BETA,
) -> "torch.Tensor":
    """Differentiable soft AABB overlap / repulsion energy.

    Each cell is a continuous rectangular potential with half-extents
    ``half + port_emission``. Pairwise penetration depths use
    ``softplus(-gap / β) · β`` so gradients stay defined at contact.
    """
    import torch
    import torch.nn.functional as F

    n = problem.n_nodes
    if n < 2:
        return xy.new_zeros(())

    half = xy.new_tensor(expanded_half_extents(problem, margin_um=margin_um))
    beta_t = xy.new_tensor(float(beta))
    acc = xy.new_zeros(())
    for i in range(n):
        for j in range(i + 1, n):
            gap_x = torch.abs(xy[i, 0] - xy[j, 0]) - (half[i, 0] + half[j, 0])
            gap_y = torch.abs(xy[i, 1] - xy[j, 1]) - (half[i, 1] + half[j, 1])
            # Soft penetration (≥0); ≈ max(0, -gap) as β→0.
            ox = F.softplus(-gap_x / beta_t) * beta_t
            oy = F.softplus(-gap_y / beta_t) * beta_t
            acc = acc + (ox * oy) ** 2
    return acc


def phase_loss_torch(
    xy: "torch.Tensor",
    problem: PlacementProblem,
    weights: Optional[ObjectiveWeights] = None,
) -> "torch.Tensor":
    """Σ_g (Δφ̂_g)² with Δφ̂ = 2π·neff·ΔL/λ from differentiable arm lengths."""
    import torch

    w = weights or ObjectiveWeights()
    k = 2.0 * math.pi * float(w.neff) / float(w.wavelength_um)
    id_to_idx = problem.node_index()
    theta = problem.theta_rad
    phi_sq = xy.new_zeros(())
    for g in problem.phase_groups:
        if len(g.arm_net_indices) < 2:
            continue
        lengths: List["torch.Tensor"] = []
        for arm in g.arm_net_indices:
            L_arm = xy.new_zeros(())
            for ni in arm:
                net = problem.nets[ni]
                i_s = id_to_idx[net.src.node_id]
                i_d = id_to_idx[net.dst.node_id]
                p_s_np, _ = port_world(problem, net.src, xy=problem.xy, theta=theta)
                p_d_np, _ = port_world(problem, net.dst, xy=problem.xy, theta=theta)
                off_s = p_s_np - problem.xy[i_s]
                off_d = p_d_np - problem.xy[i_d]
                p_s = xy[i_s] + xy.new_tensor(off_s)
                p_d = xy[i_d] + xy.new_tensor(off_d)
                delta = p_d - p_s
                L_arm = L_arm + torch.abs(delta[0]) + torch.abs(delta[1])
            lengths.append(L_arm)
        stacked = torch.stack(lengths)
        delta_L = stacked.max() - stacked.min()
        phi_sq = phi_sq + (k * delta_L) ** 2
    return phi_sq


def y_pitch_loss(
    xy: "torch.Tensor",
    problem: PlacementProblem,
    *,
    pitch_um: float = Y_CHANNEL_PITCH_UM,
    beta: float = OVERLAP_SOFTPLUS_BETA,
) -> "torch.Tensor":
    """Soft Y-channel regularization for parallel MZI / mesh arms.

    Two coupled penalties (µm):

    1. **Adjacent-arm pitch** — for each two-arm phase group, softplus when
       ``|y_arm0 − y_arm1| < pitch`` so parallel arms open ≥ ``pitch`` runway.
    2. **Discrete channel snap** — pull each node's ``y`` toward the nearest
       multiple of ``pitch`` so multi-stage I/O lands on shared horizontal
       routing tracks (reduces collinear merging / detour blisters).
    """
    import torch
    import torch.nn.functional as F

    pitch = xy.new_tensor(float(pitch_um))
    beta_t = xy.new_tensor(float(beta))
    id_to_idx = problem.node_index()
    acc = xy.new_zeros(())

    # --- (1) phase-group arm separation ---
    for g in problem.phase_groups:
        if len(g.arm_net_indices) < 2:
            continue
        arm_ys: List["torch.Tensor"] = []
        for arm in g.arm_net_indices:
            nodes: set = set()
            for ni in arm:
                net = problem.nets[ni]
                nodes.add(net.src.node_id)
                nodes.add(net.dst.node_id)
            if not nodes:
                continue
            ys = [xy[id_to_idx[nid], 1] for nid in nodes if nid in id_to_idx]
            if not ys:
                continue
            arm_ys.append(torch.stack(ys).mean())
        if len(arm_ys) < 2:
            continue
        # Sort and penalize consecutive under-pitch gaps.
        stacked = torch.stack(arm_ys)
        order = torch.argsort(stacked)
        sorted_y = stacked[order]
        for k in range(len(sorted_y) - 1):
            gap = sorted_y[k + 1] - sorted_y[k]
            short = F.softplus((pitch - gap) / beta_t) * beta_t
            acc = acc + short * short

    # --- (2) discrete channel snap for all movable cells ---
    movable = problem.movable
    for i in range(problem.n_nodes):
        if not bool(movable[i]):
            continue
        y = xy[i, 1]
        # nearest channel: pitch * round(y/pitch)
        channel = pitch * torch.round(y / pitch)
        acc = acc + (y - channel) ** 2

    return acc


def _is_stage_anchor_component(component: str) -> bool:
    c = (component or "").strip()
    return any(c.startswith(p) for p in _STAGE_ANCHOR_PREFIXES)


def _stage_from_node_id(node_id: str) -> Optional[int]:
    """Parse a mesh-column / stage index from a common builder instance id."""
    for pat in _STAGE_NAME_PATTERNS:
        m = pat.match(node_id)
        if m:
            return int(m.group(1))
    return None


def topo_stage_indices(
    problem: PlacementProblem,
    store_components: Optional[Dict[str, str]] = None,
) -> np.ndarray:
    """Assign each node a mesh-column / topological stage index.

    Preference order:

    1. **Name patterns** from mesh builders (``sw{r}_{c}`` → column ``c``,
       ``bn{s}`` / ``mzi{k}`` / ``wdm_mux{n}``, …).
    2. **Coarsened longest-path** on MMI/coupler/crossing anchors (heater
       interiors collapse) when names are unavailable.
    """
    n = problem.n_nodes
    stages = np.zeros(n, dtype=np.int64)
    if n == 0:
        return stages

    named = 0
    for i, nid in enumerate(problem.node_ids):
        s = _stage_from_node_id(nid)
        if s is not None:
            stages[i] = int(s)
            named += 1
    if named >= max(2, n // 4):
        # Enough of the netlist carries explicit column ids.
        return stages

    # --- fallback: coarsened longest-path on anchors ---
    if not problem.nets:
        return stages

    comps: Dict[str, str] = dict(store_components or {})
    is_anchor = np.ones(n, dtype=bool)
    if comps:
        for i, nid in enumerate(problem.node_ids):
            is_anchor[i] = _is_stage_anchor_component(comps.get(nid, ""))
        if not bool(is_anchor.any()):
            is_anchor[:] = True

    raw = np.zeros(n, dtype=np.int64)
    for _ in range(n + 1):
        changed = False
        for net in problem.nets:
            s, d = int(net.src.node_idx), int(net.dst.node_idx)
            # Only advance stage when leaving an anchor (column hop).
            step = 1 if bool(is_anchor[s]) else 0
            cand = int(raw[s]) + step
            if cand > int(raw[d]):
                raw[d] = cand
                changed = True
        if not changed:
            break

    # Coarsen: unique sorted depths → 0..K-1 so consecutive columns are adjacent.
    uniq = sorted({int(v) for v in raw.tolist()})
    remap = {v: i for i, v in enumerate(uniq)}
    for i in range(n):
        stages[i] = remap[int(raw[i])]
    return stages


def enforce_x_stage_gap(
    xy: np.ndarray,
    problem: PlacementProblem,
    *,
    min_gap_um: float = X_STAGE_GAP_UM,
    store_components: Optional[Dict[str, str]] = None,
) -> np.ndarray:
    """Hard post-opt snap: push later stages east until consecutive gaps ≥ min.

    Returns a copy of ``xy`` with stage cohorts rigidly translated in X.
    """
    out = np.array(xy, dtype=np.float64, copy=True)
    stage = topo_stage_indices(problem, store_components=store_components)
    unique = sorted({int(s) for s in stage.tolist()})
    if len(unique) < 2:
        return out

    for a, b in zip(unique, unique[1:]):
        idx_a = [i for i in range(problem.n_nodes) if int(stage[i]) == a]
        idx_b = [i for i in range(problem.n_nodes) if int(stage[i]) == b]
        if not idx_a or not idx_b:
            continue
        mean_a = float(np.mean(out[idx_a, 0]))
        mean_b = float(np.mean(out[idx_b, 0]))
        deficit = float(min_gap_um) - (mean_b - mean_a)
        if deficit <= 0.0:
            continue
        for s in unique:
            if s < b:
                continue
            for i in range(problem.n_nodes):
                if int(stage[i]) == s and bool(problem.movable[i]):
                    out[i, 0] += deficit
    return out


def x_stage_loss(
    xy: "torch.Tensor",
    problem: PlacementProblem,
    *,
    min_gap_um: float = X_STAGE_GAP_UM,
    beta: float = OVERLAP_SOFTPLUS_BETA,
    store_components: Optional[Dict[str, str]] = None,
) -> "torch.Tensor":
    """Soft minimum X-runway between consecutive topological mesh stages.

    For stages ``s`` and ``s+1``, softplus when
    ``mean_x(s+1) − mean_x(s) < min_gap`` so butterfly / crossbar columns
    open ≥ ``min_gap`` µm of horizontal fan-out room for LiDAR bundles.

    Also penalizes cross-stage nets whose ``|Δx|`` is under ``min_gap``.
    """
    import torch
    import torch.nn.functional as F

    stage = topo_stage_indices(problem, store_components=store_components)
    unique = sorted({int(s) for s in stage.tolist()})
    gap = xy.new_tensor(float(min_gap_um))
    beta_t = xy.new_tensor(float(beta))
    acc = xy.new_zeros(())

    if len(unique) >= 2:
        means: Dict[int, "torch.Tensor"] = {}
        for s in unique:
            idxs = [i for i in range(problem.n_nodes) if int(stage[i]) == s]
            if not idxs:
                continue
            means[s] = torch.stack([xy[i, 0] for i in idxs]).mean()
        for a, b in zip(unique, unique[1:]):
            if a not in means or b not in means:
                continue
            dx = means[b] - means[a]
            short = F.softplus((gap - dx) / beta_t) * beta_t
            acc = acc + short * short

    id_to_idx = problem.node_index()
    for net in problem.nets:
        i = id_to_idx.get(net.src.node_id)
        j = id_to_idx.get(net.dst.node_id)
        if i is None or j is None:
            continue
        if int(stage[i]) == int(stage[j]):
            continue
        dx = torch.abs(xy[i, 0] - xy[j, 0])
        short = F.softplus((gap - dx) / beta_t) * beta_t
        acc = acc + short * short
    return acc


def placement_fom_loss(
    xy: "torch.Tensor",
    problem: PlacementProblem,
    weights: Optional[ObjectiveWeights] = None,
    *,
    store_components: Optional[Dict[str, str]] = None,
) -> "torch.Tensor":
    """``λ_F·F + λ_φ·phase + λ_overlap·overlap + λ_y·y_pitch + λ_x·x_stage``."""
    w = weights or ObjectiveWeights()
    total = xy.new_zeros(())
    if w.lambda_F > 0.0:
        total = total + w.lambda_F * F_torch(
            xy, problem, w, loss_dB_per_cm=float(w.loss_dB_per_cm)
        )
    if w.lambda_phi > 0.0:
        total = total + w.lambda_phi * phase_loss_torch(xy, problem, w)
    if w.lambda_overlap > 0.0:
        total = total + w.lambda_overlap * overlap_loss(xy, problem)
    if getattr(w, "lambda_y_pitch", 0.0) > 0.0:
        pitch = float(getattr(w, "y_pitch_um", Y_CHANNEL_PITCH_UM) or Y_CHANNEL_PITCH_UM)
        total = total + float(w.lambda_y_pitch) * y_pitch_loss(
            xy, problem, pitch_um=pitch
        )
    if getattr(w, "lambda_x_stage", 0.0) > 0.0:
        gap = float(
            getattr(w, "x_stage_gap_um", X_STAGE_GAP_UM) or X_STAGE_GAP_UM
        )
        total = total + float(w.lambda_x_stage) * x_stage_loss(
            xy,
            problem,
            min_gap_um=gap,
            store_components=store_components,
        )
    return total


def hard_separation_ok(
    xy: np.ndarray,
    problem: PlacementProblem,
    *,
    margin_um: float = PORT_EMISSION_MARGIN_UM,
    eps_um: float = 1e-3,
) -> Tuple[bool, int, float]:
    """Strict AABB separation under expanded footprints.

    Returns ``(ok, n_violations, min_gap_um)`` where ``min_gap`` is the
    minimum of ``max(gap_x, gap_y)`` over pairs (positive ⇒ separated on
    at least one axis).
    """
    half = expanded_half_extents(problem, margin_um=margin_um)
    n = problem.n_nodes
    viol = 0
    min_sep = float("inf")
    for i in range(n):
        for j in range(i + 1, n):
            gap_x = abs(float(xy[i, 0] - xy[j, 0])) - (
                float(half[i, 0]) + float(half[j, 0])
            )
            gap_y = abs(float(xy[i, 1] - xy[j, 1])) - (
                float(half[i, 1]) + float(half[j, 1])
            )
            # Separated if either axis has positive clearance.
            sep = max(gap_x, gap_y)
            min_sep = min(min_sep, sep)
            if gap_x < -eps_um and gap_y < -eps_um:
                viol += 1
    if n < 2:
        return True, 0, float("inf")
    return viol == 0, viol, float(min_sep)


def F_numpy(
    problem: PlacementProblem,
    xy: Optional[np.ndarray] = None,
    weights: Optional[ObjectiveWeights] = None,
    *,
    loss_dB_per_cm: float = LOSS_DB_PER_CM,
) -> float:
    """NumPy twin of ``F_torch`` for ``evaluate_objective`` reporting."""
    if not _have_torch():
        return 0.0
    import torch

    w = weights or ObjectiveWeights()
    xy_arr = problem.xy if xy is None else xy
    t = torch.tensor(xy_arr, dtype=torch.float64)
    with torch.no_grad():
        return float(F_torch(t, problem, w, loss_dB_per_cm=loss_dB_per_cm).item())
