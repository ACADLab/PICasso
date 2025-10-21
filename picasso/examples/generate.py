"""Example: run PICasso with OpenAI backend."""
from picasso import PICasso

def main():
    engine = PICasso.with_openai()
    result = engine.generate("Design a 2x2 MMI with grating couplers for I/O.")
    print("Success:", result.success)
    for att in result.attempts:
        print(f"Attempt {att.attempt}:")
        for name, rep in att.reports.items():
            print("  ", name, rep.get("passed"), rep.get("errors"), rep.get("warnings"))

if __name__ == "__main__":
    main()
