
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator

class InstanceSpec(BaseModel):
    component: str
    settings: Dict[str, Any] = {}
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0

class Netlist(BaseModel):
    instances: Dict[str, InstanceSpec] = Field(default_factory=dict)
    connections: List[List[str]] = Field(default_factory=list)  # [[a,pa,b,pb], ...]
    ports: Dict[str, str] = Field(default_factory=dict)         # {"o1": "inst,port", ...}
    models: Dict[str, str] = Field(default_factory=dict)

    @validator("connections", each_item=True)
    def _conn_len(cls, v):
        if len(v) != 4:
            raise ValueError("each connection must be [instA, portA, instB, portB]")
        return v
