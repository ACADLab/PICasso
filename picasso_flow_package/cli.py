
import argparse, json, sys
from .pipeline import run_pipeline

def dummy_llm(resp_path: str):
    # returns a closure that "pretends" to be an LLM call by reading a file
    def _call(_prompt: str) -> str:
        with open(resp_path, "r") as f:
            return f.read()
    return _call

def main():
    ap = argparse.ArgumentParser(description="LLM -> GDS pipeline (no PnR/routing issues)")
    ap.add_argument("--problem", required=True, help="text file describing the design problem")
    ap.add_argument("--llm-json", required=True, help="path to a JSON netlist returned by an LLM")
    ap.add_argument("--out-gds", default="out.gds")
    args = ap.parse_args()

    with open(args.problem) as f:
        problem_text = f.read()

    report = run_pipeline(problem_text, llm_call=dummy_llm(args.llm_json), prefer="json", out_gds=args.out_gds)
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
