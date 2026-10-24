import argparse, json, sys
from zerowall.reports import reproduce

if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Offline deterministic analysis only; never calls a provider."
    )
    p.add_argument("pack")
    p.add_argument("--analyze-only", action="store_true", default=True)
    args = p.parse_args()
    result = reproduce(args.pack)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["all_match"] else 1)
