"""
Loss Target Configuration

Target insertion loss values extracted from Updated_Loss_Values.pptx
These targets are based on state-of-the-art research literature and
serve as validation thresholds for generated designs.

Reference: Updated_Loss_Values.pptx (root directory)
"""

# Target Insertion Loss Values (in dB)
# Format: {circuit_identifier: max_acceptable_loss_db}

LOSS_TARGETS_DB = {
    # Core Photonic Circuits (Problems 1-20)
    'mzm': 10.0,                          # Problem 1: Mach-Zehnder Modulator (10-30 dB/cm range, using lower bound)
    'ring_filter': 1.3,                   # Problem 2: Ring Resonator Add-Drop Filter
    'dual_ring_filter': 3.0,              # Problem 3: Dual-Ring Resonator Tunable Filter
    'wdm_4ch': 0.5,                       # Problem 4: 4-Channel WDM using Cascaded MZIs
    'switch_1x4': 5.5,                    # Problem 5: Tunable 1×4 Optical Switch
    'balanced_receiver': 6.5,             # Problem 6: Balanced Coherent Receiver
    'awg_16ch': 2.5,                      # Problem 7: 16-Channel AWG
    'switch_2x2': 2.0,                    # Problem 8: 2×2 Thermo-Optic Switch (0.7 dB, using 2 dB for margin)
    'y_splitter': 0.3,                    # Problem 9: Y-Branch Power Splitter
    'optical_hybrid_90': 1.5,             # Problem 10: 90-Degree Optical Hybrid
    'oadm': 1.3,                          # Problem 11: Add-Drop Multiplexer (same as ring filter)
    'ring_bank_4': 0.1,                   # Problem 12: Tunable Ring Resonator Bank (4 Rings)
    'qam_16': 1.3,                        # Problem 13: 16-QAM Modulator (same as ring filter)
    'switch_wss_1x8': 6.0,                # Problem 14: Wavelength Selective Switch (1×8)
    'grating_coupler_8ch': 8.0,           # Problem 15: Grating Coupler Array (8 Channels, per GC)
    'balanced_photodetector': float('inf'), # Problem 16: Integrated Balanced Photodetector (N/A)
    'ring_modulator_feedback': 1.3,       # Problem 17: Microring Modulator with Feedback (same as ring)
    'switch_2x2_pcm': 2.0,                # Problem 18: 2×2 Switch (PCM-based)
    'switch_16x16_dual_ring': 11.0,       # Problem 19: 16×16 Switch Based on Dual-Ring-Assisted MZI
    'optical_delay_line': 0.1,            # Problem 20: Optical Delay Line (0.08 dB/m, using 0.1 for short lengths)

    # Common Components
    'mmi_1x2': 0.3,                       # MMI 1×2 Splitter
    'mmi_1x4': 0.6,                       # MMI 1×4 Splitter
    'coupler_3db': 0.3,                   # 3 dB Directional Coupler
    'waveguide_straight': 0.1,            # Straight Waveguide (per cm, estimate)
    'waveguide_bend': 0.05,               # 90-degree Bend (estimate)

    # Generic Categories (when specific circuit not identified)
    'modulator': 10.0,                    # Generic modulator
    'filter': 3.0,                        # Generic filter
    'switch': 5.0,                        # Generic switch
    'coupler': 0.5,                       # Generic coupler
    'default': 5.0,                       # Default fallback
}

# Tolerance for "close enough" (allow designs within this margin)
TOLERANCE_DB = 1.0  # ±1 dB from target

# Component type keywords for automatic circuit detection
CIRCUIT_TYPE_KEYWORDS = {
    'mzm': ['mzm', 'mach-zehnder modulator', 'modulator mzi'],
    'ring_filter': ['ring', 'resonator', 'add-drop', 'drop filter'],
    'dual_ring_filter': ['dual ring', 'double ring', 'two ring'],
    'wdm_4ch': ['wdm', 'wavelength division', '4-channel', '4ch'],
    'switch_1x4': ['1x4 switch', '1×4 switch', 'switch 1x4'],
    'balanced_receiver': ['balanced receiver', 'coherent receiver'],
    'awg_16ch': ['awg', 'arrayed waveguide', '16-channel'],
    'switch_2x2': ['2x2 switch', '2×2 switch', 'switch 2x2'],
    'y_splitter': ['y-branch', 'y branch', 'y-splitter', 'y splitter'],
    'optical_hybrid_90': ['90 degree hybrid', '90-degree hybrid', 'optical hybrid'],
    'qam_16': ['16-qam', 'qam-16', 'qam modulator'],
    'grating_coupler_8ch': ['grating coupler', 'gc array'],
}


def get_target_loss(circuit_type: str = None, circuit_description: str = None) -> float:
    """
    Get target insertion loss for a given circuit type.

    Args:
        circuit_type: Explicit circuit type identifier
        circuit_description: Text description to parse for circuit type

    Returns:
        Target insertion loss in dB
    """
    # Direct lookup
    if circuit_type and circuit_type in LOSS_TARGETS_DB:
        return LOSS_TARGETS_DB[circuit_type]

    # Keyword-based detection from description
    if circuit_description:
        desc_lower = circuit_description.lower()
        for ctype, keywords in CIRCUIT_TYPE_KEYWORDS.items():
            if any(kw in desc_lower for kw in keywords):
                return LOSS_TARGETS_DB.get(ctype, LOSS_TARGETS_DB['default'])

    # Fallback to default
    return LOSS_TARGETS_DB['default']


def format_target_string(circuit_type: str = None) -> str:
    """
    Format a human-readable target loss string.

    Args:
        circuit_type: Circuit type identifier

    Returns:
        Formatted string like "Target: ≤ 5.0 dB"
    """
    target = get_target_loss(circuit_type)
    if target == float('inf'):
        return "Target: N/A (detector, no loss specification)"
    return f"Target: ≤ {target:.1f} dB"
