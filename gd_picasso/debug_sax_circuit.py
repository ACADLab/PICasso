"""
Debug script to understand why S-matrix is all zeros.
Tests SAX circuit evaluation step by step.
"""

import sys
from pathlib import Path
import yaml
import numpy as np

# Add parent directory to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import gdsfactory as gf
import sax
import gplugins.sax as gs

def test_simple_sax_circuit():
    """Test a simple SAX circuit to verify basic functionality."""
    print("="*80)
    print("TEST 1: Simple SAX Circuit")
    print("="*80)
    
    # Create a simple netlist
    netlist = {
        "instances": {
            "straight1": {"component": "straight"},
        },
        "connections": {},
        "ports": {
            "o1": "straight1,o1",
            "o2": "straight1,o2"
        }
    }
    
    # Create models
    models = {
        "straight": gs.models.straight
    }
    
    # Build circuit
    try:
        circ_result = sax.circuit(netlist=netlist, models=models)
        if isinstance(circ_result, tuple):
            circ = circ_result[0]
        else:
            circ = circ_result
        
        # Evaluate
        Sd = circ(length=10.0, width=0.5)
        print(f"Circuit result type: {type(Sd)}")
        print(f"Circuit result: {Sd}")
        
        # Convert to dense
        from sax import sdense
        try:
            S = sdense(Sd, ports=['o1', 'o2'])
        except:
            S = sdense(Sd)
        
        # Handle tuple return
        if isinstance(S, tuple):
            S = S[0]
        
        print(f"S-matrix shape: {S.shape}")
        print(f"S-matrix:\n{S}")
        print(f"S-matrix min: {np.min(np.abs(S)):.6f}, max: {np.max(np.abs(S)):.6f}")
        
        if np.max(np.abs(S)) > 0:
            print("✅ Simple circuit works!")
        else:
            print("❌ Simple circuit returns zero S-matrix")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_yaml_netlist():
    """Test with actual YAML netlist from a sample."""
    print("\n" + "="*80)
    print("TEST 2: YAML Netlist")
    print("="*80)
    
    # Find any YAML file for problem 1
    yaml_paths = list(Path('output').glob('*_results/*/problem_1/*/circuit.yaml'))
    if not yaml_paths:
        print(f"❌ No YAML files found for problem 1")
        return
    
    yaml_path = yaml_paths[0]
    print(f"Using YAML: {yaml_path}")
    
    with open(yaml_path) as f:
        yaml_data = yaml.safe_load(f)
    
    print(f"YAML keys: {list(yaml_data.keys())}")
    print(f"Instances: {list(yaml_data.get('instances', {}).keys())[:5]}")
    print(f"Connections: {len(yaml_data.get('connections', {}))}")
    print(f"Ports: {yaml_data.get('ports', {})}")
    
    # Create netlist for SAX - extract connections from routes if needed
    connections = yaml_data.get('connections', {})
    if not connections and 'routes' in yaml_data:
        routes = yaml_data.get('routes', {})
        if isinstance(routes, dict) and 'optical' in routes:
            optical_routes = routes['optical']
            if isinstance(optical_routes, dict) and 'links' in optical_routes:
                connections = optical_routes['links']
                print(f"Extracted {len(connections)} connections from routes.optical.links")
    
    netlist = {
        'instances': yaml_data.get('instances', {}),
        'connections': connections,
        'ports': yaml_data.get('ports', {})
    }
    
    # Check port names
    print(f"\nPort names in netlist: {list(netlist['ports'].keys())}")
    
    # Check instance components
    print(f"\nInstance components:")
    for inst_name, inst_data in list(netlist['instances'].items())[:3]:
        if isinstance(inst_data, dict):
            comp_type = inst_data.get('component', '')
            print(f"  {inst_name}: {comp_type}")
    
    # Build models
    models = {
        "straight": gs.models.straight,
        "bend_euler": gs.models.bend,
        "mmi1x2": gs.models.mmi1x2,
        "straight_heater_metal": lambda **kw: sax.sdict({('o1', 'o2'): np.exp(1j * kw.get('phi', 0.0)) * 0.9, ('o2', 'o1'): np.exp(1j * kw.get('phi', 0.0)) * 0.9, ('o1', 'o1'): 0.0, ('o2', 'o2'): 0.0})
    }
    
    # Try to build circuit
    try:
        print("\nBuilding SAX circuit...")
        circ_result = sax.circuit(netlist=netlist, models=models)
        if isinstance(circ_result, tuple):
            circ = circ_result[0]
        else:
            circ = circ_result
        
        print(f"Circuit function: {circ}")
        
        # Try to evaluate with empty params
        print("\nEvaluating circuit...")
        Sd = circ()
        print(f"Result type: {type(Sd)}")
        print(f"Result: {Sd}")
        
        # Convert to dense
        from sax import sdense
        port_list = list(netlist['ports'].keys())
        print(f"Port list: {port_list}")
        
        try:
            S = sdense(Sd, ports=port_list)
        except:
            S = sdense(Sd)
        
        # Handle tuple return
        if isinstance(S, tuple):
            S = S[0]
        
        print(f"S-matrix shape: {S.shape}")
        print(f"S-matrix:\n{S}")
        print(f"S-matrix min: {np.min(np.abs(S)):.6f}, max: {np.max(np.abs(S)):.6f}")
        
        if np.max(np.abs(S)) > 0:
            print("✅ YAML netlist works!")
        else:
            print("❌ YAML netlist returns zero S-matrix")
            print("This is the problem we need to fix!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_port_name_matching():
    """Test if port names match between netlist and models."""
    print("\n" + "="*80)
    print("TEST 3: Port Name Matching")
    print("="*80)
    
    # Test what port names gplugins.sax models expect
    try:
        straight_model = gs.models.straight
        # gplugins.sax models use Pydantic - check what params they accept
        result = straight_model(length=10.0)
        print(f"Straight model result type: {type(result)}")
        if hasattr(result, 'ports'):
            print(f"Straight model ports: {result.ports}")
        elif isinstance(result, dict) and 'ports' in result:
            print(f"Straight model ports: {result['ports']}")
        print(f"Straight model result keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
    except Exception as e:
        print(f"Error testing straight model: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_sax_circuit()
    test_yaml_netlist()
    test_port_name_matching()

