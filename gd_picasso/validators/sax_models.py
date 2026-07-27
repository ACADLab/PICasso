"""SAX compact models for PICasso validator components."""

try:
    import jax
    import jax.numpy as jnp
    import sax
    from pydantic import validate_call
except ImportError:  # pragma: no cover - handled by SAXValidator availability check
    jax = None
    jnp = None
    sax = None
    validate_call = None


if sax is not None:

    @jax.jit
    @validate_call
    def crossing(
        *,
        wl: sax.FloatArrayLike = sax.WL_C,
        wl0: sax.FloatArrayLike = sax.WL_C,
        wavelength: sax.FloatArrayLike = sax.WL_C,
        neff: sax.FloatArrayLike = 2.4,
        ng: sax.FloatArrayLike = 4.2,
        length: sax.FloatArrayLike = 8.0,
        loss_dB: sax.FloatArrayLike = 0.05,
        xtalk_dB: sax.FloatArrayLike = -40.0,
        reflection_dB: sax.FloatArrayLike = -50.0,
    ) -> sax.SDict:
        """Lossy waveguide crossing model matching gdsfactory.components.crossing.

        GDSFactory crossing ports are o1 west, o3 east, o2 north, and o4 south.
        The dominant through paths are o1<->o3 and o2<->o4.

        Args:
            wl: Wavelength in micrometers.
            wl0: Center wavelength for dispersion.
            wavelength: Alias for wl0.
            neff: Effective refractive index at the center wavelength.
            ng: Group refractive index at the center wavelength.
            length: Effective crossing length in micrometers.
            loss_dB: Through insertion loss in dB.
            xtalk_dB: Crosstalk amplitude level in dB.
            reflection_dB: Return reflection amplitude level in dB.

        Returns:
            The crossing s-matrix.
        """
        wl = jnp.asarray(wl)
        wl0 = jnp.asarray(wavelength if wavelength is not None else wl0)
        dwl = wl - wl0
        dneff_dwl = (ng - neff) / wl0
        _neff = neff - dwl * dneff_dwl
        phase = 2 * jnp.pi * _neff * length / wl

        through = jnp.asarray(10 ** (-loss_dB / 20), dtype=complex) * jnp.exp(1j * phase)
        xtalk = jnp.asarray(10 ** (xtalk_dB / 20), dtype=complex) * jnp.exp(1j * phase)
        reflection = jnp.asarray(10 ** (reflection_dB / 20), dtype=complex)

        return sax.reciprocal(
            {
                ("o1", "o3"): through,
                ("o2", "o4"): through,
                ("o1", "o2"): xtalk,
                ("o1", "o4"): xtalk,
                ("o3", "o2"): xtalk,
                ("o3", "o4"): xtalk,
                ("o1", "o1"): reflection,
                ("o2", "o2"): reflection,
                ("o3", "o3"): reflection,
                ("o4", "o4"): reflection,
            }
        )

    @jax.jit
    @validate_call
    def _straight(
        *,
        wl: sax.FloatArrayLike = sax.WL_C,
        wl0: sax.FloatArrayLike = sax.WL_C,
        neff: sax.FloatArrayLike = 2.34,
        ng: sax.FloatArrayLike = 3.4,
        length: sax.FloatArrayLike = 10.0,
        loss_dB_cm: sax.FloatArrayLike = 0.0,
    ) -> sax.SDict:
        """Dispersive straight waveguide model."""
        dwl: sax.FloatArray = sax.into[sax.FloatArray](wl) - wl0
        dneff_dwl = (ng - neff) / wl0
        _neff = neff - dwl * dneff_dwl
        phase = 2 * jnp.pi * _neff * length / wl
        amplitude = jnp.asarray(10 ** (-1e-4 * loss_dB_cm * length / 20), dtype=complex)
        transmission = amplitude * jnp.exp(1j * phase)
        p = sax.PortNamer(1, 1)
        return sax.reciprocal(
            {
                (p.in0, p.out0): transmission,
            },
        )

    @jax.jit
    @validate_call
    def spiral(
        *,
        wl: sax.FloatArrayLike = sax.WL_C,
        wl0: sax.FloatArrayLike = sax.WL_C,
        neff: sax.FloatArrayLike = 2.34,
        ng: sax.FloatArrayLike = 3.4,
        length: sax.FloatArrayLike = 1000.0,
        loss_dB_cm: sax.FloatArrayLike = 0.1,
    ) -> sax.SDict:
        """Simple spiral waveguide model.

        ```{svgbob}
        in0                 out0
         o1 ~~~~~~~~~~~~~~~ o2
        ```

        The spiral is modeled as an equivalent straight waveguide whose
        physical length equals the total optical path length of the spiral.

        Args:
            wl: Operating wavelength in micrometers.
            wl0: Reference wavelength for dispersion.
            neff: Effective refractive index.
            ng: Group refractive index.
            length: Total optical path length of the spiral in micrometers.
            loss_dB_cm: Propagation loss in dB/cm.

        Returns:
            Reciprocal 2-port S-matrix of the spiral.

        Notes:
            This model assumes the spiral behaves as a single continuous
            waveguide. It does not model:

            - bend radiation loss
            - coupling between adjacent spiral turns
            - fabrication-induced phase errors
            - polarization effects

            These effects are typically negligible for well-designed spirals
            with sufficient spacing.
        """

        return _straight(
            wl=wl,
            wl0=wl0,
            neff=neff,
            ng=ng,
            length=length,
            loss_dB_cm=loss_dB_cm,
        )

    @jax.jit
    @validate_call
    def ge_detector_straight_si_contacts(
        wl: sax.FloatArrayLike = sax.WL_C,
        absorption_dB: sax.FloatArrayLike = 40.0,
        reflection_dB: sax.FloatArrayLike = -35.0,
    ) -> sax.SDict:
        """Behavioral Ge photodetector.

        The detector is modeled as an optical termination that absorbs nearly all
        incident light with a small return reflection. Port names match
        gdsfactory.components.ge_detector_straight_si_contacts: one optical input
        (o1) and two electrical contacts (bot, top).
        """

        through = jnp.full_like(
            wl,
            10 ** (-abs(absorption_dB) / 20),
        )

        reflection = jnp.full_like(
            wl,
            10 ** (reflection_dB / 20),
        )

        zero = jnp.zeros_like(through)

        return {
            ("o1", "o1"): reflection,
            ("o1", "bot"): zero,
            ("bot", "o1"): zero,
            ("o1", "top"): zero,
            ("top", "o1"): zero,
            ("bot", "bot"): zero,
            ("top", "top"): zero,
            ("bot", "top"): zero,
            ("top", "bot"): zero,
        }

    @jax.jit
    @validate_call
    def dbr(
        *,
        wl: sax.FloatArrayLike = sax.WL_C,
        wl0: float = 1.55,
        bandwidth: float = 0.02,
        reflection_peak: float = 0.95,
        loss_dB: float = 0.0,
    ) -> sax.SDict:
        r"""Distributed Bragg Reflector (DBR).

        Simplified wavelength-selective reflector.

        Args:
            wl: Wavelength in micrometers.
            wl0: Bragg wavelength.
            bandwidth: Reflection bandwidth (sigma of Gaussian).
            reflection_peak: Peak reflected power.
            loss_dB: Insertion loss.

        Returns:
            S-matrix dictionary.
        """

        wl = jnp.asarray(wl)
        one = jnp.ones_like(wl)

        loss_amp = jnp.asarray(
            10 ** (-loss_dB / 20),
            dtype=complex,
        ) * one

        reflection = reflection_peak * jnp.exp(
            -((wl - wl0) ** 2) / (2 * bandwidth**2)
        )

        r = jnp.sqrt(reflection).astype(complex) * loss_amp
        t = jnp.sqrt(1 - reflection).astype(complex) * loss_amp

        p = sax.PortNamer(1, 1)

        return sax.reciprocal(
            {
                (p.in0, p.in0): r,
                (p.in0, p.out0): t,
                (p.out0, p.out0): r,
            }
        )

    @jax.jit
    @validate_call
    def polarization_splitter_rotator(
        wl: sax.FloatArrayLike = sax.WL_C,
        wl0: sax.FloatArrayLike = sax.WL_C,
        neff: sax.FloatArrayLike = 2.34,
        ng: sax.FloatArrayLike = 3.4,
        length: sax.FloatArrayLike = 76.33,
        loss_dB: sax.FloatArrayLike = 0.3,
        split_ratio: sax.FloatArrayLike = 0.5,
    ) -> sax.SDict:
        """Compact polarization splitter-rotator model.

        ```{svgbob}
                +-------------+     out1
                |             |---* o2
         o1 *---|     PSR     |
        in0     |             |---* o3
                +-------------+     out0
        ```

        Args:
            wl: Wavelength in micrometers.
            wl0: Center wavelength for dispersion.
            neff: Effective refractive index at the center wavelength.
            ng: Group refractive index at the center wavelength.
            length: Effective optical length in micrometers.
            loss_dB: Insertion loss in dB.
            split_ratio: Fraction of output power routed from o1 to o2.

        Returns:
            S-matrix dictionary representing a reciprocal 3-port splitter.
        """
        dwl = sax.into[sax.FloatArray](wl) - wl0
        dneff_dwl = (ng - neff) / wl0
        _neff = neff - dwl * dneff_dwl
        phase = 2 * jnp.pi * _neff * length / wl
        amplitude = jnp.asarray(10 ** (-loss_dB / 20), dtype=complex)
        transmission = amplitude * jnp.exp(1j * phase)
        split_ratio = jnp.clip(split_ratio, 0.0, 1.0)

        return sax.reciprocal(
            {
                ("o1", "o2"): transmission * split_ratio**0.5,
                ("o1", "o3"): transmission * (1 - split_ratio) ** 0.5,
            }
        )

else:

    def crossing(*args, **kwargs):
        """Placeholder used when SAX is not installed."""
        raise ImportError("SAX is required for crossing")

    def spiral(*args, **kwargs):
        """Placeholder used when SAX is not installed."""
        raise ImportError("SAX is required for spiral")

    def ge_detector_straight_si_contacts(*args, **kwargs):
        """Placeholder used when SAX is not installed."""
        raise ImportError("SAX is required for ge_detector_straight_si_contacts")

    def dbr(*args, **kwargs):
        """Placeholder used when SAX is not installed."""
        raise ImportError("SAX is required for dbr")

    def polarization_splitter_rotator(*args, **kwargs):
        """Placeholder used when SAX is not installed."""
        raise ImportError("SAX is required for polarization_splitter_rotator")


DBR = dbr

PATCHED_SAX_MODELS = {
    "crossing": crossing,
    "DBR": DBR,
    "dbr": dbr,
    "ge_detector_straight_si_contacts": ge_detector_straight_si_contacts,
    "spiral": spiral,
}


def get_patched_sax_models():
    """Return repo-owned SAX models that must override installed libraries."""
    return dict(PATCHED_SAX_MODELS)
