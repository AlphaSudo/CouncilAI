"""Audit exact Git-index bytes before publication without printing secret values."""

import json
import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    rb"sk-or-v1-[A-Za-z0-9_-]{25,}",
    rb"tvly-(?:dev-)?[A-Za-z0-9_-]{24,}",
    rb"nvapi-[A-Za-z0-9_-]{28,}",
    rb"gsk_[A-Za-z0-9]{25,}",
    rb"gh[pousr]_[A-Za-z0-9]{25,}",
    rb"sb_secret_[A-Za-z0-9_-]{24,}",
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
)


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, check=True
    ).stdout


def main():
    files = git("ls-files", "-z", "--cached").decode().strip("\0").split("\0")
    secrets = []
    for filename in (".env.local", ".env.cloud", ".env.hosted"):
        for name, value in dotenv_values(ROOT / filename).items():
            if (
                value
                and len(value) >= 16
                and any(
                    part in name for part in ("KEY", "TOKEN", "SECRET", "DATABASE_URL")
                )
            ):
                secrets.append(value.encode())
    token = ROOT / "data/director-token"
    if token.exists():
        secrets.append(token.read_bytes().strip())
    issues = []
    for filename in files:
        path = Path(filename)
        if any(
            part in {"data", ".venv", "node_modules", ".vercel", "dist", "__pycache__"}
            for part in path.parts
        ):
            issues.append((filename, "private/generated directory"))
        if (
            (path.name.startswith(".env") and path.name != ".env.example")
            or path.name == "director-token"
            or path.suffix in {".sqlite3", ".sqlite", ".db", ".pem"}
        ):
            issues.append((filename, "private file"))
        content = git("show", ":" + filename)
        if any(secret and secret in content for secret in secrets):
            issues.append((filename, "configured secret detected"))
        if any(re.search(pattern, content) for pattern in PATTERNS):
            issues.append((filename, "credential-shaped value detected"))
    if issues:
        print(json.dumps({"passed": False, "issues": issues}, indent=2))
        raise SystemExit(1)
    print(
        json.dumps(
            {"passed": True, "staged_files": len(files), "secret_values_printed": False}
        )
    )


if __name__ == "__main__":
    main()
