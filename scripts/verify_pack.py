import json, sys
from zerowall.reports import verify_pack

if __name__ == "__main__":
    try:
        print(json.dumps(verify_pack(sys.argv[1]), indent=2))
    except Exception as exc:
        print("Verification failed: " + str(exc))
        sys.exit(1)
