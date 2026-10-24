"""Optical compiler package."""

from . import ast
from .compiler import Compiler, CompileError, CompileResult
from .embedding import (
    ComponentGraph,
    EmbeddingError,
    EmbeddingProblem,
    EmbeddingResult,
    derive_puc_states,
    HostGraph,
    LabelSpec,
    build_component_graph,
)
from .puc_switching import (
    InactiveSwitchSpec,
    derive_switch_dictionary,
    load_host_graph_from_json,
    load_puc_switch_table,
)
from .graph import GraphFragment, Label
from .display import (
    component_graph_summary,
    component_graph_to_dot,
    format_expr,
    graph_fragment_summary,
    graph_fragment_to_dot,
    host_graph_summary,
    host_graph_to_dot,
    print_dot,
    export_graphviz,
    render_host_with_paths,
)
from .topology import (
    build_smartlight_mesh,
    build_feedforward_mesh,
    build_triangle_mesh,
    build_lab_simulator_mesh,
    # LAB_SIMULATOR_REFERENCE_CONFIG,
)
from .typesys import (
    OPTICAL,
    REAL,
    UNIT,
    TupleType,
    Type,
    UnitaryType,
)

__all__ = [
    "ast",
    "Compiler",
    "CompileError",
    "CompileResult",
    "GraphFragment",
    "Label",
    "LabelSpec",
    "HostGraph",
    "ComponentGraph",
    "EmbeddingProblem",
    "EmbeddingResult",
    "EmbeddingError",
    "build_component_graph",
    "derive_puc_states",
    "InactiveSwitchSpec",
    "derive_switch_dictionary",
    "load_host_graph_from_json",
    "load_puc_switch_table",
    "format_expr",
    "graph_fragment_summary",
    "graph_fragment_to_dot",
    "component_graph_summary",
    "component_graph_to_dot",
    "host_graph_summary",
    "host_graph_to_dot",
    "print_dot",
    "export_graphviz",
    "render_host_with_paths",
    "build_smartlight_mesh",
    "build_feedforward_mesh",
    "build_triangle_mesh",
    "build_lab_simulator_mesh",
    # "LAB_SIMULATOR_REFERENCE_CONFIG",
    "OPTICAL",
    "REAL",
    "UNIT",
    "TupleType",
    "Type",
    "UnitaryType",
]
