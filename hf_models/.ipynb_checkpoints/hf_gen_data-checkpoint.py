ENGINE            = 'hf'     # or 'openai'
OPENAI_API_KEY    = 'ENTER API KEY HERE'
HF_MODEL_NAME     = 'deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B'

FILE_ID           = 'file-4zemm4ei5rhvSuWtDxe2Xg'  # openai only
SAMPLES_PER_PR    = 3
REFINE_ROUNDS     = 0

COMPONENTS_PATH    = 'components.txt'
COMPONENTS_MAX_CHARS = 15000  # adjustable

##########################################################################################
##																						##
##########################################################################################

import re, textwrap, os
from pathlib import Path
import pandas as pd
from tqdm import tqdm

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
                 
routings = [
    (mmi_splitter.ports['o2'], ps1.ports['o1']),
    (mmi_splitter.ports['o3'], ps2.ports['o1']),
    (mmi_combiner.ports['o2'], ps1.ports['o2']),
    (mmi_combiner.ports['o1'], ps2.ports['o2']),
]

for p1, p2 in routings:
    gf.routing.route_single(r, port1=p1, port2=p2, cross_section='strip', radius=5)


r.add_port("o1", port=mmi_splitter.ports["o1"])\n
r.add_port("o2", port=mmi_combiner.ports["o3"])\n

r.draw_ports()\n
r.plot()\n
""")

def load_problems(path: str):
    txt = Path(path).read_text(encoding='utf-8')
    pat = re.compile(r'Problem\s+(\d+)\s*\(([^)]+)\)\s*:', re.I)
    matches = list(pat.finditer(txt))
    problems = []
    for i, m in enumerate(matches):
        idx, title = int(m.group(1)), m.group(2).strip()
        body = txt[m.end(): (matches[i+1].start() if i+1 < len(matches) else len(txt))].strip()
        if body:
            problems.append((idx, title, body))
    return problems

# load components.txt and build an augmented prompt that the model will see
def load_components_text(path: str, max_chars: int | None = None) -> str:
    try:
        raw = Path(path).read_text(encoding='utf-8')
    except FileNotFoundError:
        print(f'[WARN] {path} not found. Continuing without additional reference.')
        return ''
    if max_chars and len(raw) > max_chars:
        kept = raw[:max_chars]
        kept += f'\n[... truncated {len(raw) - max_chars} characters ...]'
        return kept
    return raw

def build_prompt_with_components(base_prompt: str, components_text: str) -> str:
    if not components_text:
        return base_prompt
    appendix = textwrap.dedent(f"""
    ---
    Reference: components.txt
    Use the following component definitions/notes when generating the code. Prefer these names, port labels, and constraints where applicable.

    Begin components.txt
    {components_text}
    End components.txt
    """).strip()
    return base_prompt.rstrip() + '\n\n' + appendix

def make_agent():
    # if ENGINE.lower() == 'openai':
    #     return HFAgent(api_key=OPENAI_API_KEY, file_id=FILE_ID)
    if ENGINE.lower() == 'hf':
        from hf_agent import HFAgent
        return HFAgent(model_name=HF_MODEL_NAME)
    else:
        raise ValueError("ENGINE must be 'openai' or 'hf'")

def run_prompt(prompt_text: str, csv_name: str, agent, problems):
    total_calls = len(problems) * SAMPLES_PER_PR * (1 + REFINE_ROUNDS)
    rows = []

    with tqdm(total=total_calls, desc=f'{csv_name} – API Calls') as bar:
        for idx, title, body in problems:
            for s in range(SAMPLES_PER_PR):
                agent.start_new_conversation()
                # first pass
                resp = agent.ASK_LLM_iterate(prompt_text, body, clear_context=True)
                rows.append([idx, title, s, 0, resp])
                bar.update(1)

                # refinement passes
                for fb in range(1, REFINE_ROUNDS + 1):
                    resp = agent.ASK_LLM_iterate(
                        prompt_text,
                        'Ensure you meet all restrictions. Refine your answer.'
                    )
                    rows.append([idx, title, s, fb, resp])
                    bar.update(1)

    pd.DataFrame(rows, columns=['problem_idx', 'problem_title',
                                'sample', 'feedback_round', 'response']
                 ).to_csv(csv_name, index=False)
    print(f'[INFO] saved {len(rows)} rows → {csv_name}')

def main():
    problems = load_problems('hf_adjusted_problems.txt')
    # read components and inject into the prompt for every call
    components_text = load_components_text(COMPONENTS_PATH, COMPONENTS_MAX_CHARS)
    prompt_with_components = build_prompt_with_components(PYTHON_PROMPT, components_text)

    agent_py = make_agent()
    run_prompt(prompt_with_components, 'llm_responses_python.csv', agent_py, problems)

if __name__ == '__main__':
    main()
