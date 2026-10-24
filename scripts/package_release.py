"""Build an allowlisted credential-free source/test-build archive. Never publishes."""

import hashlib
import json
import zipfile
from pathlib import Path

from zerowall.settings import Settings


def package(destination=None):
    s = Settings()
    root = s.root
    roots = [
        "src",
        "scripts",
        "tests",
        "contracts",
        "config",
        "benchmark",
        "plans",
        "docs",
        "deploy",
    ]
    files = {}
    for name in [
        "README.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "pyproject.toml",
        "requirements.lock",
        ".env.example",
        ".gitignore",
        ".dockerignore",
        "Dockerfile",
        "vercel.json",
    ]:
        files[name] = (root / name).read_bytes()
    for directory in roots + ["apps/web"]:
        for p in (root / directory).rglob("*"):
            relative = p.relative_to(root)
            if (
                p.is_file()
                and not any(
                    part
                    in {
                        ".venv",
                        "__pycache__",
                        ".pytest_cache",
                        "node_modules",
                        "test-results",
                        "playwright-report",
                        ".git",
                    }
                    for part in relative.parts
                )
                and p.suffix not in {".pyc", ".tsbuildinfo"}
                and not any(part.startswith("dist-") for part in relative.parts)
                and not any(
                    part.endswith((".egg-info", ".dist-info"))
                    for part in relative.parts
                )
            ):
                files[relative.as_posix()] = p.read_bytes()
    director_path = s.data / "director-token"
    director = (
        director_path.read_text(encoding="utf-8").strip()
        if director_path.exists()
        else ""
    )
    for name, content in files.items():
        if any(
            key.encode() in content
            for key in (
                s.api_key,
                s.openrouter_api_key,
                s.tavily_api_key,
                s.database_url,
                s.supabase_key,
                director,
                *s.direct_keys.values(),
            )
            if key
        ):
            raise ValueError("Credential detected; packaging refused: " + name)
    checks = {
        name: hashlib.sha256(content).hexdigest() for name, content in files.items()
    }
    source_checks = {
        name: sha
        for name, sha in checks.items()
        if name.startswith(
            (
                "src/",
                "scripts/",
                "tests/",
                "contracts/",
                "config/",
                "benchmark/",
                "deploy/",
                "apps/web/src/",
                "apps/web/e2e/",
            )
        )
        or name
        in (
            "pyproject.toml",
            "Dockerfile",
            ".dockerignore",
            "requirements.lock",
            "apps/web/package.json",
            "apps/web/package-lock.json",
            "apps/web/vite.config.ts",
            "apps/web/tsconfig.json",
            "apps/web/playwright.config.ts",
            "apps/web/index.html",
        )
    }
    source_tree_sha256 = hashlib.sha256(
        json.dumps(source_checks, sort_keys=True).encode()
    ).hexdigest()
    files["SOURCE_CHECKSUMS.json"] = json.dumps(
        checks, sort_keys=True, indent=2
    ).encode()
    output = (
        Path(destination)
        if destination
        else s.data / "releases" / "ZeroWall-local-test-build.zip"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in sorted(files.items()):
            z.writestr(name, content)
    return {
        "path": str(output),
        "files": len(files),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "published": False,
        "source_tree_sha256": source_tree_sha256,
        "local_credentials_included": False,
        "live_inference_enabled": False,
        "token_factory_requires_billing_verification": True,
        "openrouter_disabled_by_default": True,
        "direct_provider_support": ["zai", "gemini", "nvidia_nim", "groq"],
    }


if __name__ == "__main__":
    print(json.dumps(package(), indent=2))
