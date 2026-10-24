"""Fetch pinned public tokenizer data only; no credentials or model weights."""

import hashlib
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads(
        (ROOT / "config/token_factory_tokenizers.json").read_text(encoding="utf-8")
    )
    destination = ROOT / "data/tokenizers"
    destination.mkdir(parents=True, exist_ok=True)
    for model, entry in manifest["models"].items():
        path = destination / (entry["sha256"] + ".json")
        if (
            path.is_file()
            and hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
        ):
            print(f"Ready: {model}")
            continue
        response = httpx.get(entry["url"], follow_redirects=True, timeout=60)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != entry["sha256"]:
            raise ValueError(f"Published tokenizer checksum mismatch: {model}")
        temporary = path.with_suffix(".download")
        temporary.write_bytes(response.content)
        temporary.replace(path)
        print(f"Installed: {model}")


if __name__ == "__main__":
    main()
