"""Prepare an ignored local cloud-setup file; print no credentials."""

import json
import secrets
import tempfile
from pathlib import Path

from dotenv import dotenv_values


def main():
    root = Path(__file__).resolve().parents[1]
    destination = root / ".env.cloud"
    if destination.exists():
        print("Existing .env.cloud kept unchanged")
        return
    values = dotenv_values(root / "deploy/vercel.env.example")
    existing = dotenv_values(root / ".env.local")
    values["ZEROWALL_DIRECTOR_TOKEN"] = secrets.token_urlsafe(32)
    values["ZEROWALL_DATA_DIR"] = str(
        Path(tempfile.gettempdir()) / "zerowall-cloud-admin"
    )
    for key in ("NEBIUS_API_KEY", "TAVILY_API_KEY"):
        values[key] = existing.get(key) or ""
    # Exclusive creation prevents replacing an operator's populated secret file.
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(
            "# Private local cloud setup. Ignored by Git. Never paste this file into chat.\n"
        )
        stream.write(
            "# Fill Supabase URL, secret key, database URL and final public origin.\n"
        )
        stream.write(
            "# This Windows cache path is for local administration. Vercel uses /tmp/zerowall.\n"
        )
        for key, value in values.items():
            stream.write(key + "=" + json.dumps(value or "") + "\n")
    print(
        "Created ignored .env.cloud; generated a director code and reused existing provider keys. No credentials printed."
    )


if __name__ == "__main__":
    main()
