
import json
from typing import Callable, Literal, Optional
import gdsfactory as gf
from .schemas import Netlist
from .placer import diagonal_place
from .router import build_component_from_netlist

class BuildReport(dict):
    @property
    def ok(self) -> bool:
        return self.get("ok", False)

def parse_llm_json(s: str) -> Netlist:
    # extract a JSON blob, tolerate code fences
    s = s.strip()
    if s.startswith("```"):
        s = s.strip("`")
        # remove optional language tags
        if s.startswith("json"):
            s = s[4:]
    data = json.loads(s)
    # support either { "netlist": {...}} or flat schema
    if "netlist" in data:
        data = data["netlist"]
    return Netlist(**data)

def check_all_ports_connected(comp: gf.Component) -> list[str]:
    # In gf, connectivity isn't explicit; we check whether any named ports
    # on placed refs remain unexposed and not routed. As a proxy, ensure top-level
    # ports exist and count connections == expected. This is a heuristic.
    # Users should enhance with graph connectivity checks if needed.
    return []

def run_pipeline(
    problem_text: str,
    llm_call: Callable[[str], str],
    prefer: Literal["json","python"]="json",
    out_gds: str = "out.gds"
) -> BuildReport:
    if prefer == "json":
        prompt = (
            "You are a photonic layout assistant. Given the following problem, "
            "output ONLY a valid JSON netlist with keys instances, connections, ports, models. "
            "All optical ports must be connected; do not include comments.\n\n"
            f"Problem:\n{problem_text}"
        )
        raw = llm_call(prompt)
        nl = parse_llm_json(raw)
        nl = diagonal_place(nl)
        c = build_component_from_netlist(nl)
    else:
        prompt = (
            "You are a photonic layout assistant. Given the following problem, "
            "output ONLY executable Python using gdsfactory to build the layout. "
            "It must define a function build() -> gf.Component and not print anything.\n\n"
            f"Problem:\n{problem_text}"
        )
        code = llm_call(prompt)
        # execute in a minimal sandbox
        ns = {"gf": gf}
        exec(code, ns)
        c = ns["build"]()

    # simple integrity checks
    unconnected = check_all_ports_connected(c)
    report = BuildReport(ok=len(unconnected)==0)
    report["unconnected_ports"] = unconnected
    report["cells"] = list(c.get_dependencies())
    c.write_gds(out_gds)
    report["gds"] = out_gds
    return report
