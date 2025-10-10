import re, textwrap
from pathlib import Path
import pandas as pd
from tqdm import tqdm
from openAI_llms.agent import LLMAgent  

MY_API_KEY = "ENTER_API_KEY_HERE"
SAMPLES_PER_PR  = 3
REFINE_ROUNDS   = 0

JSON_PROMPT = textwrap.dedent(""" 
    Write me ONLY a complete JSON photonic netlist (no extra prose) for the problem above.
    The JSON must contain top-level keys "instance", "connections", "ports", and "models".\n
    
    You must adhere to the following restrictions:\n
        - Ensure all optical ports are connected\n
        - Do not include any comments\n
        - Ports are labeled o1, o2, o3, ... such that the bottom-left port is o1, then ports are labelled moving clockwise\n
    
    Follow the following JSON netlist template:\n
    <<< JSON Netlist Template >>>\n
    {\n
    "netlist":{\n
        "instances": {\n
        "<component_name1>": "<component>",\n
        "<component_name2>": {'component': '<component>', 'settings': {'<parameter>': <value>}}\n
        ...\n
        },\n
        "connections": {\n
        "<component_name>,<port>": "<component_name>,<port>",\n
        ...\n
        },\n
        "ports": {\n
        "<port_name>": "<component_name>,<port>",\n
        ...\n
        }\n
    },\n
    "models":{\n
        "<component>": "<ref>",\n
        ...\n
    }\n
    }
""")

PYTHON_PROMPT = textwrap.dedent("""
Write me ONLY complete Python code (no extra prose) for the problem above.
Write the python code to instantiate the circuit in GDSFactory 9.9.4. 
Follow the following structure for creating the circuit:\n
  1. Instantiate all components (with settings)\n
  2. Move parts to avoid overlap (DRC-safe)\n
  3. Connect ports with route_single\n
  4. Expose external ports\n

Restrictions (immutable across problems):\n
  - Only use GDSFactory components & port names\n
  - Ensure all optical ports connected\n
  - No comments / extraneous text\n
  - Ports labelled o1, o2, … clockwise\n
  - Do not create custom names for any models/components, use the id's specified in the problem\n
  - route_single expects (component, port1, port2, cross_section)\n
  - Use single quotes around strings, avoid double quotes like ""xx""\n
                                
Use the following example for your reference:\n
import gdsfactory as gf\n

r = gf.Component()\n

mmi_splitter = r.add_ref(gf.components.mmi(inputs=1, outputs=2))\n
mmi_splitter.move((0,0))\n

mmi_combiner = r.add_ref(gf.components.mmi(inputs=2, outputs=1))\n
mmi_combiner.move((200, 0))\n

ps1 = r.add_ref(gf.components.straight_heater_metal(length=10))\n
ps1.move((100, 20))\n

ps2 = r.add_ref(gf.components.straight_heater_metal(length=10))\n
ps2.move((100, -20))\n

route = gf.routing.route_single(
    r,
    port1=mmi_splitter.ports["o2"],
    port2=ps1.ports["o1"],
    cross_section="strip",
    radius=5,
)\n

route2 = gf.routing.route_single(
    r,
    port1=mmi_splitter.ports["o3"],
    port2=ps2.ports["o1"],
    cross_section="strip",
    radius=5,
)\n

route3 = gf.routing.route_single(
    r,
    port1=mmi_combiner.ports["o2"],
    port2=ps1.ports["o2"],
    cross_section="strip",
    radius=5,
)\n

route4 = gf.routing.route_single(
    r,
    port1=mmi_combiner.ports["o1"],
    port2=ps2.ports["o2"],
    cross_section="strip",
    radius=5,
)\n

r.add_port("o1", port=mmi_splitter.ports["o1"])\n
r.add_port("o2", port=mmi_combiner.ports["o3"])\n

r.draw_ports()\n
r.plot()\n
""")


def load_problems(path: str):
    txt = Path(path).read_text(encoding="utf-8")
    pat = re.compile(r"Problem\s+(\d+)\s*\(([^)]+)\)\s*:", re.I)
    matches = list(pat.finditer(txt))
    out = []
    for i, m in enumerate(matches):
        idx, title = int(m.group(1)), m.group(2).strip()
        start = m.end()
        end   = matches[i + 1].start() if i + 1 < len(matches) else len(txt)
        body  = txt[start:end].strip()
        if body:
            out.append((idx, title, body))
    return out


def run_prompt(prompt_text: str, csv_name: str, agent: LLMAgent, problems):
    total_calls = len(problems) * SAMPLES_PER_PR * (1 + REFINE_ROUNDS)
    rows = []

    with tqdm(total=total_calls, desc=f"API Calls – {csv_name}") as bar:
        for idx, title, body in problems:
            for s in range(SAMPLES_PER_PR):
                agent.start_new_conversation()
                resp = agent.ASK_LLM_iterate(prompt_text, body, clear_context=True)
                rows.append([idx, title, s, 0, resp])
                bar.update(1)

                for fb in range(1, REFINE_ROUNDS + 1):
                    resp = agent.ASK_LLM_iterate(
                        prompt_text,
                        "Ensure you are adhering to all the restrictions aforemention. Refine your answer and "
                        "make changes in <result>."
                    )
                    rows.append([idx, title, s, fb, resp])
                    bar.update(1)

    pd.DataFrame(
        rows,
        columns=["problem_idx", "problem_title", "sample",
                 "feedback_round", "response"]
    ).to_csv(csv_name, index=False)
    print(f"[INFO] saved {len(rows)} rows to {csv_name}")


def main():
    problems = load_problems("problems.txt")
    agent = LLMAgent(api_key=MY_API_KEY, file_id="file-4zemm4ei5rhvSuWtDxe2Xg")

    run_prompt(PYTHON_PROMPT, "llm_responses_python.csv", agent, problems)
    run_prompt(JSON_PROMPT, "llm_responses_json.csv", LLMAgent(api_key=MY_API_KEY, pdf_path=None), problems)


if __name__ == "__main__":
    main()

