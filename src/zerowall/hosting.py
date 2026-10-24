"""Opt-in single-director hosting. Local entry and spending policy stay separate."""

import os
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Hosting:
    hosted: bool = False
    public_origin: str = ""
    director_token: str = ""

    @classmethod
    def from_env(cls):
        mode = os.environ.get("ZEROWALL_MODE", "local")
        if mode not in ("local", "hosted"):
            raise ValueError("ZEROWALL_MODE must be local or hosted")
        if mode == "local":
            return cls()
        origin = os.environ.get("ZEROWALL_PUBLIC_ORIGIN", "")
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or "*" in parsed.netloc
        ):
            raise ValueError(
                "Hosted mode requires one HTTPS ZEROWALL_PUBLIC_ORIGIN without a path"
            )
        # Validate the port too; urlsplit defers its validation until accessed.
        port = parsed.port
        host = parsed.hostname
        if ":" in host:
            host = f"[{host}]"
        origin = f"https://{host}" + (f":{port}" if port not in (None, 443) else "")
        token = os.environ.get("ZEROWALL_DIRECTOR_TOKEN", "")
        if (
            not 32 <= len(token) <= 200
            or not token.isascii()
            or any(c.isspace() for c in token)
        ):
            raise ValueError(
                "Hosted mode requires a secret ZEROWALL_DIRECTOR_TOKEN of 32–200 ASCII characters without whitespace"
            )
        directory = os.environ.get("ZEROWALL_DATA_DIR", "")
        if not directory or not Path(directory).is_absolute():
            raise ValueError(
                "Hosted mode requires an absolute ZEROWALL_DATA_DIR on persistent storage"
            )
        if os.environ.get("ZEROWALL_STORAGE", "local") != "supabase" and (
            os.environ.get("ZEROWALL_PERSISTENT_STORAGE_CONFIRMED", "").lower()
            != "true"
        ):
            raise ValueError(
                "Mount persistent storage and set ZEROWALL_PERSISTENT_STORAGE_CONFIRMED=true"
            )
        return cls(True, origin, token)

    @property
    def allowed_hosts(self):
        hosts = ["127.0.0.1", "localhost"]
        if self.hosted:
            hosts.append(urlsplit(self.public_origin).hostname)
        else:
            hosts.append("testserver")
        return hosts


def validate_runtime(settings, store=None, worker=True):
    """No inference: check the selected persistence authority before serving."""
    if not (settings.frontend / "index.html").is_file():
        raise ValueError("Build the frontend before starting a hosted server")
    with tempfile.TemporaryFile(dir=settings.data) as probe:
        probe.write(b"storage-check")
        probe.flush()
    if getattr(settings, "database_url", ""):
        if store is None or not store.healthy():
            raise ValueError("Shared database readiness check failed")
    else:
        with closing(sqlite3.connect(settings.data / "zerowall.sqlite3")) as connection:
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Hosted database integrity check failed")
    from .context_window import tokenizer

    if worker:
        for model in settings.policy["council_default_models"]:
            tokenizer(model)
