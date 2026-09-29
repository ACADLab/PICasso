"""
Behavioral FoM: waveguide IL must track loss_dB_cm × L (nonzero).

Catches the split-brain where SAXValidator used library
``straight(loss_dB_cm=0.0)`` while the PCG gate used ``build_lossy_models``.
"""

from __future__ import annotations

import math

import pytest


@pytest.mark.parametrize("length_um", [100.0, 1000.0, 10000.0])
def test_straight_il_tracks_lossy_factory(length_um: float) -> None:
    pytest.importorskip("sax")
    pytest.importorskip("jax")
    pytest.importorskip("gplugins")

    import jax.numpy as jnp
    from gplugins import sax as gs

    from gd_picasso.pcg.sax_models import (
        DEFAULT_LOSS_DB_CM,
        build_lossy_models,
        ensure_jax_x64,
    )

    ensure_jax_x64()
    models = build_lossy_models(DEFAULT_LOSS_DB_CM)
    straight = models["straight"]

    # Direct model call — same factory the gate / validator share
    S = straight(wl=1.55, length=length_um)
    # gplugins returns dict keyed by port-pair tuples
    key = ("o2", "o1")
    if key not in S:
        key = ("o1", "o2")
    t = float(jnp.abs(S[key]) ** 2)
    il_db = -10.0 * math.log10(max(t, 1e-30))

    expected = DEFAULT_LOSS_DB_CM * (length_um / 1e4)  # µm → cm
    assert il_db > 0.0, "lossy factory must not yield structurally zero IL"
    assert abs(il_db - expected) < 1e-6, (
        f"IL={il_db:.6f} dB != {DEFAULT_LOSS_DB_CM}×L/1e4={expected:.6f} "
        f"(L={length_um} µm)"
    )

    # Contrast: library default is the silent-null we are killing
    S0 = gs.models.straight(wl=1.55, length=length_um, loss_dB_cm=0.0)
    t0 = float(jnp.abs(S0[key]) ** 2)
    il0 = -10.0 * math.log10(max(t0, 1e-30))
    assert il0 < 1e-9, "control: loss_dB_cm=0.0 must be ~zero IL"


def test_sax_validator_uses_lossy_factory() -> None:
    """SAXValidator model path must share build_lossy_models (not loss=0)."""
    import inspect

    from gd_picasso.validators import sax_validator as mod

    src = inspect.getsource(mod.SAXValidator._check_sax_compilation)
    assert "build_lossy_models" in src
    # Must not register the zero-loss library straight as the primary model map
    assert "models = {\n                        \"straight\": gs.models.straight," not in src
    assert 'models = {"straight": gs.models.straight' not in src.replace(" ", "")
