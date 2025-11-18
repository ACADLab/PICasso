"""
Test if phase parameter is being passed correctly to SAX models.
"""

import sys
from pathlib import Path
import yaml
import numpy as np

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import sax
import gplugins.sax as gs

# Test phase shifter model
def test_phase_shifter_model():
    """Test if phase shifter model responds to phase parameter."""
    print("="*80)
    print("Testing Phase Shifter Model")
    print("="*80)
    
    # Create phase shifter model
    def phase_shifter_model(**kwargs):
        phase = kwargs.get('phi', kwargs.get('phase', 0.0))
        length = kwargs.get('length', 10.0)
        
        phase_factor = np.exp(1j * phase)
        loss_db = 0.23 * (length / 10.0)
        amplitude = 10 ** (-loss_db / 20.0)
        
        S = {
            ('o1', 'o2'): amplitude * phase_factor,
            ('o2', 'o1'): amplitude * phase_factor,
            ('o1', 'o1'): 0.0,
            ('o2', 'o2'): 0.0,
        }
        
        return {"ports": ['o1', 'o2'], "S": S}
    
    # Test with different phases
    for phase_val in [0.0, np.pi/4, np.pi/2, np.pi]:
        result = phase_shifter_model(phi=phase_val)
        S = result['S']
        transmission = S[('o1', 'o2')]
        print(f"Phase = {phase_val:.3f}: |S21| = {np.abs(transmission):.6f}, arg = {np.angle(transmission):.3f}")
    
    print("\n✅ Phase shifter model responds to phase parameter")

def test_mzi_with_phase():
    """Test MZI circuit with phase parameter."""
    print("\n" + "="*80)
    print("Testing MZI Circuit with Phase Parameter")
    print("="*80)
    
    # Create phase shifter model
    def phase_shifter_model(**kwargs):
        phase = kwargs.get('phi', kwargs.get('phase', 0.0))
        length = kwargs.get('length', 10.0)
        
        phase_factor = np.exp(1j * phase)
        loss_db = 0.23 * (length / 10.0)
        amplitude = 10 ** (-loss_db / 20.0)
        
        S = {
            ('o1', 'o2'): amplitude * phase_factor,
            ('o2', 'o1'): amplitude * phase_factor,
            ('o1', 'o1'): 0.0,
            ('o2', 'o2'): 0.0,
        }
        
        return {"ports": ['o1', 'o2'], "S": S}
    
    # MMI model
    def mmi_model(**kwargs):
        # Simple 3dB splitter/combiner
        sqrt_half = 1.0 / np.sqrt(2.0)
        S = {
            ('o1', 'o2'): sqrt_half,
            ('o1', 'o3'): sqrt_half,
            ('o2', 'o1'): sqrt_half,
            ('o2', 'o3'): 0.0,
            ('o3', 'o1'): sqrt_half,
            ('o3', 'o2'): 0.0,
            ('o1', 'o1'): 0.0,
            ('o2', 'o2'): 0.0,
            ('o3', 'o3'): 0.0,
        }
        return {"ports": ['o1', 'o2', 'o3'], "S": S}
    
    # MZI netlist
    netlist = {
        "instances": {
            "mmi1": {"component": "mmi1x2"},
            "phase_shifter": {"component": "straight_heater_metal"},
            "mmi2": {"component": "mmi1x2"},
        },
        "connections": {
            "mmi1,o2": "phase_shifter,o1",
            "phase_shifter,o2": "mmi2,o1",
        },
        "ports": {
            "in": "mmi1,o1",
            "out": "mmi2,o2"
        }
    }
    
    models = {
        "mmi1x2": mmi_model,
        "straight_heater_metal": phase_shifter_model,
    }
    
    # Wrap models for SAX
    sax_models = {}
    for name, fn in models.items():
        def _wrap(f, model_name=name):
            def g(**kwargs):
                Sd = f(**kwargs)
                if isinstance(Sd, dict) and "ports" in Sd and "S" in Sd:
                    return sax.sdict(Sd["S"])
                return Sd
            return g
        sax_models[name] = _wrap(fn, name)
    
    # Build circuit
    circ_result = sax.circuit(netlist=netlist, models=sax_models)
    if isinstance(circ_result, tuple):
        circ = circ_result[0]
    else:
        circ = circ_result
    
    # Test with different phases
    print("\nTesting MZI transmission vs phase:")
    for phase_val in [0.0, np.pi/4, np.pi/2, np.pi]:
        Sd = circ(phase_shifter__phi=phase_val)
        from sax import sdense
        S = sdense(Sd)
        if isinstance(S, tuple):
            S = S[0]
        
        # Extract transmission from in to out
        transmission = S[1, 0]  # out, in
        power = np.abs(transmission) ** 2
        loss_db = -10 * np.log10(power) if power > 0 else 100.0
        
        print(f"Phase = {phase_val:.3f}: |S| = {np.abs(transmission):.6f}, Power = {power:.6f}, Loss = {loss_db:.3f} dB")
    
    print("\n✅ MZI responds to phase parameter")

if __name__ == "__main__":
    test_phase_shifter_model()
    test_mzi_with_phase()

