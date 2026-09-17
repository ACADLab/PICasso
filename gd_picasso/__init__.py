"""gd_picasso: YAML DSL framework for photonic circuit design."""

# Float32 goes stiff near interference nulls — require x64 on FoM path.
try:
    from gd_picasso.pcg.sax_models import ensure_jax_x64

    ensure_jax_x64()
except Exception:
    pass
