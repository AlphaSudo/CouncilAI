"""Search runs for each reply, never adds a model turn or blocks its answer."""

import json
from copy import deepcopy
from uuid import uuid4

import httpx
import pytest
from test_council_chat import drain
from test_token_factory_generation import sse
from test_token_factory_research import setup_testing

from zerowall.db import DomainError
from zerowall.research_execution import transport_tools


def setup(
    client,
    app,
    monkeypatch,
    *,
    enabled=None,
    fail=False,
    toggle_after_first=False,
    collective=False,
    planner_failure=None,
):
    r = setup_testing(app, include_beam=True)
    r.settings.tavily_api_key = "synthetic-search-key"
    searches, physical, toggles = [], [], []
    monkeypatch.setattr(
        r.tools.provider,
        "allowance",
        lambda: {"plan": "Researcher", "used": 0, "limit": 1000},
    )

    def search(**args):
        searches.append(args)
        if fail:
            raise DomainError("Synthetic search service unavailable", 429)
        item = {
            "title": "Primary engineering source",
            "url": "https://example.com/evidence",
            "content": "An exact saved passage about reversible engineering pilots and their limitations.",
        }
        return {
            "query": args["query"],
            "results": [
                {
                    "title": item["title"],
                    "url": item["url"],
                    "snippet": item["content"],
                    "rank": 1,
                }
            ],
            "raw_response": {"results": [item]},
        }

    monkeypatch.setattr(r.tools.provider, "search", search)
    original = httpx.Client

    def handler(request):
        body = json.loads(request.content)
        if (
            "Choose one focused public web-search query"
            in body["messages"][1]["content"]
        ):
            physical.append({"phase": "research_plan", "body": body})
            if (
                planner_failure == "unknown"
                and body["model"] == r.settings.policy["council_default_models"][1]
            ):
                raise httpx.ReadTimeout("Synthetic unknown query-planning outcome")
            answer = json.dumps(
                {
                    "research_actions": [
                        {
                            "name": "web_search",
                            "arguments": {
                                "query": "Research evidence " + body["model"],
                                "limit": 3,
                            },
                        }
                    ]
                }
            )
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=sse(body["model"], text=answer),
            )
        with r.store.tx() as c:
            chat = json.loads(
                c.execute(
                    "SELECT body FROM records WHERE kind='chat' ORDER BY rowid DESC LIMIT 1"
                ).fetchone()[0]
            )
            turn = r.chat.next_turn(chat, r.chat.messages(c, chat), c)
            answer = (
                "A reversible pilot should be tested against practical limitations. This is a synthetic proposal."
                if turn["phase"] in ("opening", "synthesis")
                else r.chat.review.demo(c, chat, r.chat.messages(c, chat), turn)
            )
        physical.append({"phase": turn["phase"], "body": body})
        if toggle_after_first and len(physical) == 1:
            toggled = client.post(
                f"/api/chats/{chat['id']}/research/settings",
                headers={"Idempotency-Key": str(uuid4())},
                json={"enabled": False},
            )
            assert toggled.is_success, toggled.text
            toggles.append(toggled.json())
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=sse(body["model"], text=answer),
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    body = {
        "provider": "nebius_token_factory",
        "models": r.settings.policy["council_default_models"],
        "prompt": "Compare reversible engineering pilots and their limitations.",
        "budget_usd": 24,
        "spending_scope": "shared_existing_credit",
        "review_protocol": "reviewed_v4",
    }
    if enabled is not None:
        body["search_web"] = enabled
    if collective is not None:
        body["collective_research"] = collective
    response = client.post(
        "/api/chats", headers={"Idempotency-Key": str(uuid4())}, json=body
    )
    assert response.is_success, response.text
    return r, response.json(), searches, physical, toggles


def test_default_on_searches_every_model_stage_with_real_saved_passages_and_no_extra_model_turn(
    client, app, monkeypatch
):
    r, initial, searches, physical, _ = setup(client, app, monkeypatch)
    assert initial["chat"]["research_enabled"] is True
    assert not searches and not physical
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert len(physical) == 10
    replies = [m for m in view["messages"] if m["role"] == "assistant"]
    assert len(replies) == 10 and all(
        m["web_search"]["status"] == "completed" for m in replies
    )
    assert len(searches) == 6  # Same opening / repair queries reuse the recent result.
    assert sum(m["web_search"]["reused"] for m in replies) == 4
    assert all(len(s["query"]) <= 400 for s in searches)
    for request in physical:
        messages = request["body"]["messages"]
        assert "Web search is enabled for this reply" in messages[0]["content"]
        assert "An exact saved passage" in messages[1]["content"]
    with r.store.tx() as c:
        receipts = r.store.list(c, "response_search", initial["chat"]["mission_id"])
        assert len(receipts) == 10
        openings = [x for x in receipts if x["phase"] == "opening"]
        assert len({x["snapshot_id"] for x in openings}) == 1
        assert all(x["source_version_ids"] for x in openings)
        for m in replies:
            assert r.store.get(c, m["call_id"], "call")["web_search"] == m["web_search"]


def test_off_performs_no_search_or_search_claim(client, app, monkeypatch):
    _, initial, searches, physical, _ = setup(client, app, monkeypatch, enabled=False)
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed"
    assert not searches and len(physical) == 10
    assert all(
        "Web search is enabled" not in p["body"]["messages"][0]["content"]
        for p in physical
    )
    assert all(not m.get("web_search") for m in view["messages"])


def test_search_failure_is_disclosed_without_interrupting_any_model_or_retrying_same_query(
    client, app, monkeypatch
):
    _, initial, searches, physical, _ = setup(client, app, monkeypatch, fail=True)
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert len(physical) == 10 and len(searches) == 6
    replies = [m for m in view["messages"] if m["role"] == "assistant"]
    assert all(m["web_search"]["status"] == "unavailable" for m in replies)
    assert all(m["web_search"]["reason"] for m in replies)


def test_switching_off_during_generation_keeps_current_reply_and_stops_next_searches(
    client, app, monkeypatch
):
    _, initial, searches, physical, toggles = setup(
        client, app, monkeypatch, toggle_after_first=True
    )
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert len(physical) == 10 and len(searches) == 1
    assert toggles[0]["chat"]["next_turn_research_enabled"] is False
    replies = [m for m in view["messages"] if m["role"] == "assistant"]
    assert replies[0]["web_search"]["status"] == "completed"
    assert all(not m.get("web_search") for m in replies[1:])
    assert not view["chat"]["research_enabled"]


def test_manual_retry_reuses_saved_reply_search_and_preserves_credit_receipts(
    client, app, monkeypatch
):
    r, initial, searches, _, _ = setup(client, app, monkeypatch)
    from zerowall.council_web_search import prepare

    turn = initial["next_turn"]

    with r.store.tx() as c:
        chat = r.store.get(c, initial["chat"]["id"], "chat")
        turn = r.chat.next_turn(chat, r.chat.messages(c, chat), c)
    first = prepare(r, chat, turn, "synthetic-logical-turn", lambda: False)
    with r.store.tx() as c:
        credits = deepcopy(r.store.list(c, "search_credit", chat["mission_id"]))
    second = prepare(r, chat, turn, "synthetic-logical-turn", lambda: False)
    assert second == first and len(searches) == 1
    with r.store.tx() as c:
        assert r.store.list(c, "search_credit", chat["mission_id"]) == credits


@pytest.mark.parametrize(
    "provider", ["gemini", "groq", "zai", "nvidia_nim", "nebius_token_factory"]
)
def test_every_model_transport_gets_search_instruction_and_retains_its_output_settings(
    provider,
):
    request = (
        {
            "generationConfig": {"maxOutputTokens": 4096},
            "systemInstruction": {"parts": [{"text": "Original policy"}]},
            "contents": [{"role": "user", "parts": [{"text": "Question"}]}],
        }
        if provider == "gemini"
        else {
            "max_completion_tokens": 4096,
            "messages": [
                {"role": "system", "content": "Original policy"},
                {"role": "user", "content": "Question"},
            ],
        }
    )
    options = {
        "catalogue": [],
        "history": [],
        "mode": "structured",
        "prefix": "Saved search passages",
        "web_search": {
            "status": "completed",
            "query": "Actual public query",
            "result_count": 3,
            "reused": True,
        },
    }
    actual = transport_tools({"provider": provider}, request, options)
    system = (
        actual["systemInstruction"]["parts"][0]["text"]
        if provider == "gemini"
        else actual["messages"][0]["content"]
    )
    assert (
        "Original policy" in system and "Web search is enabled for this reply" in system
    )
    assert (
        "Actual public query" in system and "Cached search results are reuse" in system
    )
    assert (
        actual["generationConfig"]["maxOutputTokens"]
        if provider == "gemini"
        else actual["max_completion_tokens"]
    ) == 4096


def test_long_root_does_not_hide_the_latest_request_from_automatic_queries(
    client, app, monkeypatch
):
    r, initial, searches, _, _ = setup(client, app, monkeypatch)
    from zerowall.council_web_search import prepare

    turn = initial["next_turn"]

    with r.store.tx() as c:
        chat = r.store.get(c, initial["chat"]["id"], "chat")
        record = r.chat.review.record(c, chat)
        record["contract"]["question"] = (
            "Root engineering question " * 40
            + "\n\nCurrent director request:\nNEW_LATENCY_CONSTRAINT"
        )
        r.store.put(c, "chat_review", record)
        r.chat.message(
            c,
            chat,
            role="user",
            phase="intervention",
            review_cycle=record["cycle"],
            content="NEW_LATENCY_CONSTRAINT",
        )
    result = prepare(r, chat, turn, "latest-request-search", lambda: False)
    assert (
        result["status"] == "completed"
        and "NEW_LATENCY_CONSTRAINT" in searches[0]["query"]
    )


def test_query_excerpts_stay_readable_without_false_document_change_notices(
    client, app, monkeypatch
):
    r, initial, _, _, _ = setup(client, app, monkeypatch)
    chat = initial["chat"]
    previous = r.library.ingest(
        chat,
        b"An earlier search excerpt, not the full page.",
        title="One page",
        url="https://example.com/page",
        metadata={
            "origin": "search_snippet",
            "query": "first query",
            "search_policy": "per-reply-search/1",
        },
    )
    with r.store.tx() as c:
        r.store.put(
            c,
            "citation_binding",
            {
                "id": "prior-search-citation",
                "mission_id": chat["mission_id"],
                "chat_id": chat["id"],
                "version_id": previous["id"],
                "message_id": "old-public-message",
            },
        )
    latest = r.library.ingest(
        chat,
        b"Another query returns another excerpt from the same page.",
        title="One page",
        url="https://example.com/page",
        metadata={
            "origin": "search_snippet",
            "query": "second query",
            "search_policy": "per-reply-search/1",
        },
    )
    with r.store.tx() as c:
        snapshot = r.library.snapshot(c, chat, "search-variant-check")
        assert {previous["id"], latest["id"]} <= set(snapshot["version_ids"])
        assert not r.library.pending_changes(c, chat)


def test_repeated_search_snippet_never_replaces_a_saved_full_document(
    client, app, monkeypatch
):
    r, initial, _, _, _ = setup(client, app, monkeypatch)
    chat = initial["chat"]
    metadata = {
        "origin": "search_snippet",
        "query": "a query",
        "search_policy": "per-reply-search/1",
    }
    snippet = r.library.ingest(
        chat,
        b"Short saved excerpt.",
        title="A document",
        url="https://example.com/full",
        metadata=metadata,
    )
    full = r.library.ingest(
        chat,
        b"The full saved page with its context and qualifications.",
        title="A document",
        url="https://example.com/full",
        metadata={"origin": "public_url"},
    )
    repeated = r.library.ingest(
        chat,
        b"Short saved excerpt.",
        title="A document",
        url="https://example.com/full",
        metadata=metadata,
    )
    assert repeated["id"] == snippet["id"] and repeated["origin"] == "search_snippet"
    with r.store.tx() as c:
        source = r.store.get(c, full["source_id"], "source")
        assert source["current_version_id"] == full["id"]
