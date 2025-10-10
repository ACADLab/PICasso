
from typing import Dict
from .schemas import Netlist

def diagonal_place(nl: Netlist, step: float = 50.0) -> Netlist:
    """Ensure each instance has an (x,y); place along a diagonal if missing."""
    x = 0.0
    y = 0.0
    for name, inst in nl.instances.items():
        if inst.x == 0.0 and inst.y == 0.0:
            inst.x = x
            inst.y = y
            x += step
            y += step/2.0
    return nl
