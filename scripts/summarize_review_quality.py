"""Summarize a frozen, human-labelled pair manifest without API calls or credentials."""

import argparse
import json
from pathlib import Path
from zerowall.quality import summarize_quality

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("manifest")
args = parser.parse_args()
content = Path(args.manifest).read_bytes()
if len(content) > 5_000_000:
    raise ValueError("Evaluation manifest exceeds its size bound")
print(json.dumps(summarize_quality(json.loads(content)), indent=2))
