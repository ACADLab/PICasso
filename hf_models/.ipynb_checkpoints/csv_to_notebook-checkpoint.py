#!/usr/bin/env python3
"""
CSV → Jupyter Notebook converter.

Input CSV must have columns:
- problem_idx
- problem_title
- sample
- feedback_round
- response

For each row, this creates:
1) A Markdown cell: "## {problem_title} — Sample {sample}"
2) A Code cell with the exact contents of `response`.

Usage:
    python csv_to_ipynb.py input.csv output.ipynb

Requires:
    pip install nbformat
"""
import sys
import csv
from pathlib import Path
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell


def _try_int(x):
    try:
        return int(x)
    except Exception:
        return x


def csv_to_notebook(csv_path: Path, output_path: Path):
    # Read rows
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"problem_idx", "problem_title", "sample", "feedback_round", "response"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

        rows = list(reader)

    # Optional: sort for a stable, sensible order
    rows.sort(key=lambda r: (
        _try_int(r.get("problem_idx", "")),
        _try_int(r.get("sample", "")),
        _try_int(r.get("feedback_round", "")),
    ))

    # Build notebook
    nb = new_notebook(
        metadata={
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3",
                "mimetype": "text/x-python",
                "file_extension": ".py",
            },
        }
    )

    cells = []

    # Optional cover cell
    cells.append(new_markdown_cell("# Problems Notebook\n\nGenerated from CSV."))

    # Create cells per row
    for r in rows:
        title = r.get("problem_title", "").strip()
        sample = str(r.get("sample", "")).strip()
        response = r.get("response", "")

        # 1) Markdown cell with problem title + sample number
        md = f"## {title} — Sample {sample}"
        cells.append(new_markdown_cell(md))

        # 2) Code cell with the response (exact text)
        # If your responses aren't Python code, that's fine—this still stores them as a code block.
        cells.append(new_code_cell(response if response is not None else ""))

    nb["cells"] = cells

    # Write notebook
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        nbformat.write(nb, f)


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print("Usage: python csv_to_ipynb.py input.csv output.ipynb", file=sys.stderr)
        sys.exit(1)

    csv_path = Path(argv[0])
    out_path = Path(argv[1])

    if not csv_path.exists():
        print(f"Error: input CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    csv_to_notebook(csv_path, out_path)
    print(f"Wrote notebook to: {out_path}")


if __name__ == "__main__":
    main()

