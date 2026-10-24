"""Usage: python scripts/verify_review_pack.py path/to/review.zip"""
import argparse
import json
from zerowall.review_exports import verify_review_pack

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("pack")
args = parser.parse_args()
print(json.dumps(verify_review_pack(args.pack), indent=2))
