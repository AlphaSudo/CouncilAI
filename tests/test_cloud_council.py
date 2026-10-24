"""Independent API/worker instances against the real integration database."""

import json
import logging
import shutil
import time
from copy import deepcopy

import httpx
from fastapi.testclient import TestClient
from test_council_chat import drain
from test_token_factory_research import setup_testing

from zerowall.api import create_app
from zerowall.settings import Settings


def instance(path, dsn):
    settings = Settings(path)
    settings.database_url = dsn
    settings.role = "web"
    settings.api_key = "test-cloud-inference-never-network"
    settings.tavily_api_key = ""
    settings.direct_keys = {}
    settings.openrouter_enabled = False
    settings.supabase_url = "https://example.supabase.co"
    settings.supabase_key = "test-private-storage"
    return create_app(settings, run_worker=False)


def login(app):
    client = TestClient(app)
    client.headers["X-ZeroWall-Director"] = "1"
    assert client.post(
        "/api/session", json={"token": app.state.research.settings.director_token}
    ).is_success
    return client


def post(client, route, value, key):
    response = client.post(route, json=value, headers={"Idempotency-Key": key})
    assert response.is_success, response.text
    return response.json()


def test_complete_two_cycles_sources_exports_and_replacement_api(pg, tmp_path):
    api = instance(tmp_path / "web", pg.dsn)
    worker = instance(tmp_path / "worker", pg.dsn)
    worker.state.executor.ownership.acquire()
    client = login(api)
    initial = post(
        client,
        "/api/chats",
        {
            "prompt": "Compare approaches with evidence and assumptions.",
            "provider": "fixture",
            "models": ["demo/analyst", "demo/critic", "demo/builder"],
            "review_protocol": "reviewed_v4",
        },
        "new-chat",
    )
    cid = initial["chat"]["id"]
    post(
        client,
        f"/api/chats/{cid}/library/import",
        {
            "title": "Reference",
            "text": "A bandwidth baseline is essential. Compare latency and throughput.",
        },
        "import-reference",
    )
    drain(worker)
    first = client.get("/api/chats/" + cid).json()
    assert first["chat"]["status"] == "completed", first["chat"].get("error")
    assert [m["phase"] for m in first["messages"]] == [
        "prompt",
        "opening",
        "opening",
        "opening",
        "extraction",
        "scrutiny",
        "repair",
        "repair",
        "repair",
        "recheck",
        "synthesis",
    ]
    post(
        client,
        f"/api/chats/{cid}/messages",
        {"text": "Now compare implementation complexity."},
        "second-cycle",
    )
    drain(worker)
    second = client.get("/api/chats/" + cid).json()
    assert second["chat"]["status"] == "completed", second["chat"].get("error")
    assert second["messages"][: len(first["messages"])] == first["messages"]
    exported = post(client, f"/api/chats/{cid}/review/exports", {}, "review-export")
    before = client.get(exported["download"]).content
    files = api.state.research.artifacts.files
    # The independent worker can read the source bytes with no shared local disk.
    with worker.state.research.store.tx() as c:
        chat = worker.state.research.store.get(c, cid, "chat")
        hits = worker.state.research.library.search(c, chat, "bandwidth")
        assert hits["index"] == "postgres_fts" and hits["results"]
    # Destroy ALL API-local runtime files; the next instance has a new path.
    client.close()
    api.state.research.store.close()
    files.objects.close()
    logger = logging.getLogger(
        "zerowall.requests." + str(api.state.research.settings.data)
    )
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    shutil.rmtree(tmp_path / "web")
    replacement = instance(tmp_path / "replacement", pg.dsn)
    replacement_client = login(replacement)
    restored = replacement_client.get("/api/chats/" + cid).json()
    assert restored["messages"] == second["messages"]
    assert replacement_client.get(exported["download"]).content == before
    library = replacement.state.research.library
    with replacement.state.research.store.tx() as c:
        versions = replacement.state.research.store.list(
            c, "source_version", restored["chat"]["mission_id"]
        )
    assert versions
    assert b"bandwidth" in library.read_blob(versions[0]["text_sha256"])
    with replacement.state.research.store.tx() as c:
        assert replacement.state.research.budget.summary(c)["absolute_cap_usd"] == 24
    for app, connection in ((worker, None), (replacement, replacement_client)):
        if connection:
            connection.close()
        app.state.research.store.close()
        app.state.research.artifacts.files.objects.close()
    worker.state.executor.ownership.release()


def test_cloud_preserves_real_model_lineup_usage_originals_and_unknown_guard(
    pg, tmp_path, monkeypatch
):
    app = instance(tmp_path / "api", pg.dsn)
    client = login(app)
    research = app.state.research
    with pg.tx() as c:
        pg.set_setting(
            c, "cloud_ledger_ready", {"origin": "dedicated integration fixture"}
        )
        c.execute(
            "INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",
            (
                "previous-unknown",
                "previous-mission",
                "previous-call",
                230000,
                None,
                "unknown",
                "{}",
            ),
        )
    setup_testing(app, include_beam=True)
    expected = [
        "nvidia/Nemotron-3.5-Super-VL",
        "reflection/beam",
        "deepseek-ai/DeepSeek-V4-Flash-0731",
    ]
    assert research.settings.policy["council_default_models"] == expected
    initial = post(
        client,
        "/api/chats",
        {
            "prompt": "Compare engineering designs and give a practical recommendation.",
            "provider": "nebius_token_factory",
            "models": expected,
            "review_protocol": "reviewed_v4",
            "budget_usd": 24,
            "spending_scope": "shared_existing_credit",
            "search_web": False,
        },
        "real-model-fixture",
    )
    cid = initial["chat"]["id"]
    physical = []
    original_client = httpx.Client

    def respond(request):
        assert request.url.host == "api.tokenfactory.nebius.com"
        body = json.loads(request.content)
        with research.store.tx() as c:
            chat = research.store.get(c, cid, "chat")
            messages = research.chat.messages(c, chat)
            turn = research.chat.next_turn(chat, messages, c)
            if turn["phase"] == "opening":
                demo = deepcopy(turn)
                demo["participant"]["model"] = [
                    "demo/analyst",
                    "demo/critic",
                    "demo/builder",
                ][len(physical) % 3]
                text = research.chat.demo_answer(chat, messages, demo)
            else:
                text = research.chat.review.demo(c, chat, messages, turn)
        physical.append(body["model"])
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [{"finish_reason": "stop", "message": {"content": text}}],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "prompt_tokens_details": {"cached_tokens": 20},
                    "completion_tokens_details": {"reasoning_tokens": 10},
                },
            },
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kwargs: original_client(
            **kwargs, transport=httpx.MockTransport(respond)
        ),
    )
    app.state.executor.ownership.acquire()
    try:
        drain(app)
        view = client.get("/api/chats/" + cid).json()
        assert view["chat"]["status"] == "completed", view["chat"].get("error")
        assert len(physical) == 10
        assert physical[:3] == expected
        for message in view["messages"]:
            if message["role"] == "assistant":
                original = client.get(
                    f"/api/chats/{cid}/messages/{message['id']}/original"
                )
                assert original.is_success and original.json()["content"]
        with pg.tx() as c:
            money = research.budget.summary(c)
            assert money["unknown_usd"] == 0.23
            assert money["settled_usd"] > 0
            assert money["operational_cap_usd"] == 24
            assert c.execute("SELECT COUNT(*) FROM blob_files").fetchone()[0] > 0
            assert all(
                row["state"] == "settled"
                for row in c.execute(
                    "SELECT state FROM reservations WHERE mission_id=? AND state!='released'",
                    (initial["chat"]["mission_id"],),
                )
            )
    finally:
        app.state.executor.ownership.release()
        client.close()
        research.store.close()
        research.artifacts.files.objects.close()


def test_background_worker_wakes_for_an_api_job_and_releases_ownership(pg, tmp_path):
    app = instance(tmp_path / "api", pg.dsn)
    worker = instance(tmp_path / "daemon", pg.dsn)
    client = login(app)
    executor = worker.state.executor
    # Keep every file operation offline, including the actual mirror thread.
    objects = {}
    remote = worker.state.research.artifacts.files.objects
    remote.put = lambda key, data: objects.setdefault(key, data)
    remote.get = lambda key: objects[key]
    remote.delete = lambda key: objects.pop(key, None)
    executor.start()
    try:
        initial = post(
            client,
            "/api/chats",
            {
                "prompt": "Compare practical alternatives and give a recommendation.",
                "provider": "fixture",
                "models": ["demo/analyst", "demo/critic", "demo/builder"],
                "review_protocol": "reviewed_v4",
            },
            "background-council",
        )
        cid = initial["chat"]["id"]
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            current = client.get("/api/chats/" + cid).json()
            if current["chat"]["status"] != "running":
                break
            time.sleep(0.1)
        assert current["chat"]["status"] == "completed", current["chat"].get("error")
        assert not app.state.executor.thread
    finally:
        executor.draining.set()
        executor.thread.join(timeout=15)
        executor.close()
        assert not executor.thread.is_alive()
        client.close()
        for value in (app, worker):
            value.state.research.store.close()
            value.state.research.artifacts.files.objects.close()
