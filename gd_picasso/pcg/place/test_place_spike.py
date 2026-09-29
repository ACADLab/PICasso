"""
Lane Place spike smoke test — ESTIMATOR_ONLY.

Runs multi-start GD on mzi / mzm / mzi_unbalanced; φ ablation is only
claimed when arms can unbalance (mzi_unbalanced).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from gd_picasso.pcg import from_gf_yaml
from gd_picasso.pcg.place import (
    ESTIMATOR_ONLY_BANNER,
    ObjectiveWeights,
    build_placement_problem,
    estimator_fidelity,
    place_multistart,
)
from gd_picasso.pcg.place.estimator_fidelity import phi_ablation_eligible
from gd_picasso.pcg.place.objective import evaluate_objective

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name: str):
    return from_gf_yaml((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("fixture", ["mzi.yaml", "mzm.yaml", "mzi_unbalanced.yaml"])
def test_place_smoke_estimator_only(fixture: str):
    from gd_picasso.pcg.place.estimator_fidelity import plant_estimated_lengths

    store = _load(fixture)
    problem = build_placement_problem(store)
    assert problem.n_nodes >= 3
    assert len(problem.nets) >= 2

    # Plant seed lengths before optimize so fidelity has a fixed reference.
    planted = plant_estimated_lengths(store, problem)

    result = place_multistart(
        store,
        weights=ObjectiveWeights(lambda_D=0.05, lambda_phi=0.0, alpha=1.4),
        n_starts=3,
        steps=25,
        lr=1.5,
        seed=1,
        write_back=True,
        problem=problem,
    )
    assert ESTIMATOR_ONLY_BANNER.split("—")[0].strip() in result.banner
    assert result.terms.total <= result.start_terms.total + 1e-6
    # Write-back reached the store
    for nid, (x, y) in zip(problem.node_ids, result.xy):
        node = store.nodes[nid]
        assert node.x is not None and abs(node.x - x) < 1e-6
        assert node.y is not None and abs(node.y - y) < 1e-6

    # Predictions at final xy vs lengths planted at the seed (ESTIMATOR_ONLY).
    fid = estimator_fidelity(
        store,
        problem=problem,
        xy=result.xy,
        reference_um=planted,
        treat_edge_length_as="planted",
    )
    assert "ESTIMATOR_ONLY" in fid.banner
    assert fid.mode == "planted"
    assert fid.mae_um >= 0.0
    print("\n".join(fid.summary_lines()))
def test_phi_ablation_on_unbalanced_mzi():
    """λ_φ reduces estimated arm Δφ vs W_cos+D alone — only on unbalanced seed."""
    store = _load("mzi_unbalanced.yaml")
    problem = build_placement_problem(store)
    assert phi_ablation_eligible(problem), "unbalanced MZI must expose phase groups"

    start = evaluate_objective(problem)
    assert start.phi_sq > 1e-3, (
        "seed arm imbalance too small for φ ablation "
        f"(phi_sq={start.phi_sq})"
    )

    w_geo = ObjectiveWeights(lambda_D=0.05, lambda_phi=0.0, alpha=1.4)
    w_phi = ObjectiveWeights(lambda_D=0.05, lambda_phi=5e-4, alpha=1.4)

    # Fresh stores so write-back does not couple the two runs
    store_geo = _load("mzi_unbalanced.yaml")
    store_phi = _load("mzi_unbalanced.yaml")
    prob_geo = build_placement_problem(store_geo)
    prob_phi = build_placement_problem(store_phi)

    r_geo = place_multistart(
        store_geo, weights=w_geo, n_starts=4, steps=35, lr=1.5, seed=2,
        problem=prob_geo,
    )
    r_phi = place_multistart(
        store_phi, weights=w_phi, n_starts=4, steps=35, lr=1.5, seed=2,
        problem=prob_phi,
    )

    assert "ESTIMATOR_ONLY" in r_geo.banner
    # Phase term should pull Δφ̂ down relative to geometry-only (or at least
    # not increase phi_sq when starting from the same seeds).
    assert r_phi.terms.phi_sq <= r_geo.terms.phi_sq + 1e-6, (
        f"φ ablation failed: phi_sq geo={r_geo.terms.phi_sq:.4g} "
        f"phi={r_phi.terms.phi_sq:.4g} (ESTIMATOR_ONLY)"
    )


def test_stock_mzi_phase_group_present_but_balanced_seed():
    """Stock mzi has arms; symmetric seed → small φ_sq (ablation not claimed)."""
    store = _load("mzi.yaml")
    problem = build_placement_problem(store)
    assert phi_ablation_eligible(problem)
    terms = evaluate_objective(problem)
    # Symmetric fixture: residual imbalance from port table only
    assert terms.phi_sq < 50.0  # soft; far below unbalanced seed
