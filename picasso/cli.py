"""Simple CLI to run PICasso on a text prompt."""
from __future__ import annotations

import argparse
import sys
from .generator import PICasso


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PICasso: generate and validate PIC layouts")
    parser.add_argument("prompt", help="Design request, e.g., '50:50 MMI with grating couplers'")
    parser.add_argument("--backend", choices=["openai", "hf"], default="openai")
    parser.add_argument("--attempts", type=int, default=3, help="Max retry attempts")
    args = parser.parse_args(argv)

    if args.backend == "openai":
        engine = PICasso.with_openai()
    else:
        engine = PICasso.with_huggingface()

    engine.retry.max_attempts = args.attempts
    res = engine.generate(args.prompt)

    print("SUCCESS:", res.success)
    print("ATTEMPTS:", len(res.attempts))
    if res.best_code:
        print("\n--- Best code (may be from the last attempt) ---\n")
        print(res.best_code)

    # Exit code helps CI/automation detect failures
    return 0 if res.success else 2


if __name__ == "__main__":
    raise SystemExit(main())
