"""Offline release checks against saved state; never repeats the live pilots."""

import hashlib
import io
import json
import os
import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from zerowall.api import create_app
from zerowall.settings import Settings
from zerowall.source_exports import export_values, verify_extension


def main():
    root = Path(__file__).resolve().parents[1]
    baseline = json.loads(
        (root / "data/baseline-1.05.json").read_text(encoding="utf-8")
    )
    with sqlite3.connect(
        f"file:{root / 'data/zerowall.sqlite3'}?mode=ro", uri=True
    ) as c:
        originals = dict(c.execute("SELECT id,body FROM records"))
    mismatches = [
        rid
        for rid, sha in baseline["original_records"].items()
        if rid not in originals
        or hashlib.sha256(originals[rid].encode()).hexdigest() != sha
    ]
    frozen_names = {
        "council_review_v1.py",
        "council_review_v2.py",
        "council_review_v3.py",
        "review_policy_v1.py",
        "review_policy_v2.py",
        "review_policy_v3.py",
        "review_policy.py",
        "direct_models.json",
    }
    frozen = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() == sha
        for name, sha in baseline["files"].items()
        if Path(name).name in frozen_names
    }
    pilot = json.loads(
        (root / "docs/validation/research-live-1.05.json").read_text(encoding="utf-8")
    )
    settings = Settings(root / "data/research-live-1.05")
    r = create_app(settings, run_worker=False).state.research
    with r.store.tx() as c:
        chat = r.store.get(c, pilot["chat_id"], "chat")
        stored = r.store.list(c, "usage_record", chat["mission_id"])
        before = {x["id"]: x["cost"] for x in stored}
        projection = r.accounting.projection(c, chat)
        assert all(x["cost"] == before[x["id"]] for x in projection["attempts"])
        values = export_values(r, c, chat)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, content in values.items():
            z.writestr(name, content)
    with zipfile.ZipFile(buffer) as z:
        replay = verify_extension(z)
    keys = [
        settings.api_key,
        settings.openrouter_api_key,
        settings.tavily_api_key,
        settings.director_token,
        *settings.direct_keys.values(),
    ]
    keys.append((root / "data/director-token").read_text(encoding="utf-8").strip())
    assert not any(
        key in (content if isinstance(content, str) else content.decode("utf-8"))
        for key in keys
        if key
        for content in values.values()
    )
    scan = [
        p
        for directory in ("apps/web/dist", "docs")
        for p in (root / directory).rglob("*")
        if p.is_file()
    ]
    scan += [p for p in (root / "data").rglob("requests.log") if p.is_file()]
    for path in scan:
        content = path.read_bytes()
        assert not any(key.encode() in content for key in keys if key), (
            "Configured credential found in release surface"
        )
    empty = {m["key_env"]: "" for m in settings.direct_policy["models"]}
    empty.update(
        NEBIUS_API_KEY="",
        OPENROUTER_API_KEY="",
        TAVILY_API_KEY="",
        ZEROWALL_DIRECT_FREE_CONFIRMED="false",
        ZEROWALL_OPENROUTER_ENABLED="false",
    )
    with (
        patch.dict(os.environ, empty),
        patch(
            "httpx.HTTPTransport.handle_request",
            side_effect=AssertionError("Unexpected external HTTP call"),
        ),
    ):
        clean = create_app(
            Settings(root / "data/credential-free-1.05"), run_worker=False
        )
        with TestClient(clean) as client:
            client.headers["X-ZeroWall-Director"] = "1"
            assert client.post(
                "/api/session",
                json={"token": clean.state.research.settings.director_token},
            ).is_success
            response = client.get("/api/chats/bootstrap")
            assert response.is_success
            assert not clean.state.research.settings.tavily_api_key
            assert not any(clean.state.research.settings.direct_keys.values())
    assert (
        not mismatches and all(frozen.values()) and replay["accounting"] == "reproduced"
    )
    report = {
        "status": "passed",
        "original_records_checked": len(baseline["original_records"]),
        "original_record_mismatches": mismatches,
        "frozen_files": frozen,
        "live_pilot_saved_cost_assessments_preserved": len(before),
        "offline_source_and_cost_replay": replay,
        "source_export_configured_secret_scan": "passed",
        "credential_free_startup": "passed",
        "asset_document_query_log_secret_scan_files": len(scan),
        "new_model_calls": 0,
        "new_search_calls": 0,
    }
    (root / "docs/validation/research-preservation-1.05.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
