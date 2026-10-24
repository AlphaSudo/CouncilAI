import json
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

from .hosting import Hosting

ROOT = Path(__file__).resolve().parents[2]


class Settings:
    def __init__(self, data_dir=None):
        load_dotenv(ROOT / ".env.local", override=False)
        self.storage_backend = os.environ.get("ZEROWALL_STORAGE", "local")
        if self.storage_backend not in ("local", "supabase"):
            raise ValueError("ZEROWALL_STORAGE must be local or supabase")
        self.role = os.environ.get(
            "ZEROWALL_ROLE", "web" if self.storage_backend == "supabase" else "combined"
        )
        if self.role not in ("combined", "web", "worker"):
            raise ValueError("ZEROWALL_ROLE must be combined, web or worker")
        self.database_url = (
            os.environ.get("ZEROWALL_DATABASE_URL", "")
            if self.storage_backend == "supabase"
            else ""
        )
        self.supabase_url = os.environ.get("SUPABASE_URL", "")
        self.supabase_key = os.environ.get("SUPABASE_SECRET_KEY", "")
        self.supabase_bucket = os.environ.get(
            "ZEROWALL_STORAGE_BUCKET", "zerowall-private"
        )
        if self.storage_backend == "supabase":
            from urllib.parse import parse_qs, urlsplit

            parsed = urlsplit(self.database_url)
            if (
                parsed.scheme not in ("postgres", "postgresql")
                or not parsed.hostname
                or parsed.port == 6543
            ):
                raise ValueError(
                    "Supabase storage requires a Postgres direct or session-pooler URL, not transaction port 6543"
                )
            if parsed.hostname not in ("127.0.0.1", "localhost") and parse_qs(
                parsed.query
            ).get("sslmode", [""])[0] not in ("require", "verify-full", "verify-ca"):
                raise ValueError("The remote database URL must require TLS")
            storage_url = urlsplit(self.supabase_url)
            if (
                storage_url.scheme != "https"
                or not storage_url.hostname
                or storage_url.username
                or storage_url.password
                or storage_url.path not in ("", "/")
                or storage_url.query
                or storage_url.fragment
                or not self.supabase_key
            ):
                raise ValueError(
                    "Supabase storage requires an HTTPS SUPABASE_URL and a server-only SUPABASE_SECRET_KEY"
                )
        self.hosting = Hosting.from_env()
        self.root = ROOT
        self.data = Path(
            data_dir or os.environ.get("ZEROWALL_DATA_DIR", ROOT / "data")
        ).resolve()
        self.data.mkdir(parents=True, exist_ok=True)
        self.artifacts = self.data / "artifacts"
        self.artifacts.mkdir(exist_ok=True)
        self.api_key = os.environ.get("NEBIUS_API_KEY", "")
        self.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.tavily_api_key = os.environ.get("TAVILY_API_KEY", "")
        self.search_monthly_limit = min(
            900, max(0, int(os.environ.get("ZEROWALL_SEARCH_MONTHLY_LIMIT", "900")))
        )
        # Exact Gemini native continuation was live verified; other providers use structured actions by default.
        self.native_research_providers = set(
            filter(
                None,
                os.environ.get("ZEROWALL_NATIVE_RESEARCH_PROVIDERS", "gemini").split(
                    ","
                ),
            )
        )
        self.openrouter_enabled = (
            os.environ.get("ZEROWALL_OPENROUTER_ENABLED", "false").lower() == "true"
        )
        self.direct_policy = json.loads(
            (ROOT / "config/direct_models.json").read_text(encoding="utf-8")
        )
        self.direct_keys = {
            m["provider"]: os.environ.get(m["key_env"], "")
            for m in self.direct_policy["models"]
        }
        self.direct_free_confirmed = (
            os.environ.get("ZEROWALL_DIRECT_FREE_CONFIRMED", "false").lower() == "true"
        )
        self.policy = json.loads(
            (ROOT / "config/model_policy.json").read_text(encoding="utf-8")
        )
        self.models = self.policy["priority_order"]
        self.token_factory_generation = json.loads(
            (ROOT / "config/token_factory_generation.json").read_text(encoding="utf-8")
        )
        self.base_url = self.policy["base_url"].rstrip("/")
        if self.hosting.hosted:
            self.director_token = self.hosting.director_token
        else:
            token_file = self.data / "director-token"
            if not token_file.exists():
                token_file.write_text(secrets.token_urlsafe(32), encoding="utf-8")
            self.director_token = token_file.read_text(encoding="utf-8").strip()
        self.frontend = Path(
            os.environ.get("ZEROWALL_FRONTEND_DIR", ROOT / "apps/web/dist")
        )
        self.cookie_secure = self.hosting.hosted
