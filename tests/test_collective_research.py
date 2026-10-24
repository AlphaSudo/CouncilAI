"""The shared research barrier is durable, parallel and honest about coverage."""

import threading
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4

import pytest
from test_council_chat import drain
from test_per_reply_search import setup

from zerowall.collective_research import prepare
from zerowall.db import DomainError
from zerowall.web_fetch import public_addresses as real_public_addresses


def collective_setup(
    client,
    app,
    monkeypatch,
    *,
    partial=False,
    failed_extract=False,
    planner_failure=None,
):
    r, initial, _, physical, _ = setup(
        client, app, monkeypatch, collective=None, planner_failure=planner_failure
    )
    searches, extracts = [], []

    def search(**args):
        searches.append(args)
        suffix = sha256(args["query"].encode()).hexdigest()[:8]
        items = [
            {
                "title": "Shared foundation",
                "url": "https://example.com/shared",
                "content": "A shared paper excerpt.",
            },
            {
                "title": "An independent lead",
                "url": "https://example.com/" + suffix,
                "content": "An independent research excerpt.",
            },
        ]
        return {
            "query": args["query"],
            "results": [
                {
                    "title": x["title"],
                    "url": x["url"],
                    "snippet": x["content"],
                    "rank": i + 1,
                }
                for i, x in enumerate(items)
            ],
            "raw_response": {"results": items},
        }

    def extract(urls):
        extracts.append(list(urls))
        if failed_extract:
            raise DomainError("Synthetic extraction failed", 503)
        selected = urls[:1] if partial else urls
        return {
            "results": [
                {
                    "url": url,
                    "raw_content": "# FULL_PAGE\nPublic source "
                    + url
                    + "\nBoundaries and limitations are retained.\n",
                }
                for url in selected
            ],
            "failed_results": [
                {"url": url, "error": "Unavailable"}
                for url in urls
                if url not in selected
            ],
            "usage": {"credits": 1},
        }

    monkeypatch.setattr(r.tools.provider, "search", search)
    monkeypatch.setattr(r.tools.provider, "extract", extract)
    monkeypatch.setattr(
        "zerowall.web_fetch.public_addresses", lambda *args: ["93.184.216.34"]
    )
    return r, initial, physical, searches, extracts


def test_three_model_research_plans_and_searches_are_parallel_before_any_answer(
    client, app, monkeypatch
):
    r, initial, physical, searches, extracts = collective_setup(
        client, app, monkeypatch
    )
    assert initial["chat"]["collective_research_enabled"]
    planning_gate, search_gate = threading.Barrier(3), threading.Barrier(3)
    original_call, original_search = r.provider.call, r.tools.provider.search
    lock = threading.Lock()
    active, peak = 0, 0

    def call(*args, **kwargs):
        nonlocal active, peak
        if kwargs["purpose"].startswith("collective-research:"):
            with lock:
                active += 1
                peak = max(peak, active)
            planning_gate.wait(timeout=10)
            try:
                return original_call(*args, **kwargs)
            finally:
                with lock:
                    active -= 1
        with r.store.tx() as c:
            cohort = r.store.list(
                c, "collective_research", initial["chat"]["mission_id"]
            )[0]
            assert cohort["state"] == "ready" and cohort["extracted_pages"] == 4
        return original_call(*args, **kwargs)

    def web_search(**args):
        if len(searches) < 3:
            search_gate.wait(timeout=10)
        return original_search(**args)

    monkeypatch.setattr(r.provider, "call", call)
    monkeypatch.setattr(r.tools.provider, "search", web_search)
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert peak == 3 and len(physical) == 13
    cohort = view["collective_research"]
    assert cohort["state"] == "ready" and cohort["peer_answers_seen"] is False
    assert len(cohort["members"]) == 3 and all(
        m["query_origin"] == "model" for m in cohort["members"]
    )
    assert len({m["query"] for m in cohort["members"]}) == 3
    assert len(extracts) == 1 and len(extracts[0]) == 4
    shared = next(p for p in cohort["pages"] if p["url"].endswith("/shared"))
    assert len(shared["contributors"]) == 3
    openings = [m for m in view["messages"] if m["phase"] == "opening"]
    assert len(openings) == 3
    assert all(
        m["web_search"]["collective_research_id"] == cohort["id"] for m in openings
    )
    assert all(m["web_search"]["extracted_pages"] == 4 for m in openings)
    packets = [p for p in view["context_packs"] if p["namespace"]["role"] == "opening"]
    assert len({p["snapshot_id"] for p in packets}) == 1
    assert all(
        {p["version_id"] for p in packet["passages"]}
        == set(cohort["preferred_version_ids"])
        for packet in packets
    )
    for attempt in physical:
        if attempt["phase"] == "opening":
            assert (
                "other researchers as well as your own discoveries"
                in attempt["body"]["messages"][0]["content"]
            )
            assert attempt["body"]["messages"][1]["content"].count("FULL_PAGE") == 4
            assert (
                "This is a synthetic proposal"
                not in attempt["body"]["messages"][1]["content"]
            )
    assert (
        sum(x["attempt_class"] == "research" for x in view["accounting"]["attempts"])
        == 3
    )
    assert view["accounting"]["total"]["attempts"] == 13


@pytest.mark.parametrize("partial,failed", [(True, False), (False, True)])
def test_partial_or_failed_extraction_keeps_the_full_answer_flow_and_shared_excerpts(
    client, app, monkeypatch, partial, failed
):
    _, initial, physical, _, _ = collective_setup(
        client, app, monkeypatch, partial=partial, failed_extract=failed
    )
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert (
        len(physical) == 13
        and len([m for m in view["messages"] if m["role"] == "assistant"]) == 10
    )
    cohort = view["collective_research"]
    assert cohort["state"] == "limited" and cohort["source_count"] == 4
    assert cohort["extracted_pages"] == (1 if partial else 0)
    assert any(p["access"] == "search_snippet_only" for p in cohort["pages"])
    assert all(
        m["web_search"]["shared_source_count"] == 4
        for m in view["messages"]
        if m["phase"] == "opening"
    )


def test_unknown_planning_charge_stays_counted_without_automatic_retry_or_answer_interruption(
    client, app, monkeypatch
):
    r, initial, physical, _, _ = collective_setup(
        client, app, monkeypatch, planner_failure="unknown"
    )
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert (
        len(physical) == 13
        and view["budget"]["unknown_usd"] > 0
        and view["unknown_paid_attempts"] == 1
    )
    failed = next(
        m
        for m in view["collective_research"]["members"]
        if m["query_origin"] == "fallback"
    )
    assert failed["planning_outcome"] == "unknown"
    with r.store.tx() as c:
        original = deepcopy(r.store.get(c, failed["call_id"], "call"))
        money = [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY id")
        ]
    again = prepare(r, view["chat"], lambda: False)
    assert again["id"] == view["collective_research"]["id"] and len(physical) == 13
    with r.store.tx() as c:
        assert r.store.get(c, failed["call_id"], "call") == original
        assert [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY id")
        ] == money


def test_supplied_documents_survive_the_common_pool_and_followups_get_a_new_research_boundary(
    client, app, monkeypatch
):
    r, initial, physical, _, _ = collective_setup(client, app, monkeypatch)
    supplied = r.library.ingest(
        initial["chat"],
        b"Mandatory supplied constraints and qualifications.",
        title="Director's constraints",
    )
    drain(app)
    cid = initial["chat"]["id"]
    before = client.get("/api/chats/" + cid).json()
    assert supplied["id"] in before["collective_research"]["preferred_version_ids"]
    original = deepcopy(before["collective_research"])
    # An existing chat adopts the new research phase on its next explicit turn.
    with r.store.tx() as c:
        saved_chat = r.store.get(c, cid, "chat")
        saved_chat.pop("collective_research_enabled")
        r.store.put(c, "chat", saved_chat)
    result = client.post(
        f"/api/chats/{cid}/messages",
        headers={"Idempotency-Key": str(uuid4())},
        json={"text": "Now compare the latency tradeoffs."},
    )
    assert result.is_success, result.text
    drain(app)
    after = client.get("/api/chats/" + cid).json()
    assert after["chat"]["status"] == "completed", after["chat"].get("error")
    assert after["chat"]["collective_research_enabled"] is True
    assert after["collective_research"]["id"] != original["id"]
    assert len(physical) == 26
    with r.store.tx() as c:
        saved = r.store.get(c, original["id"], "collective_research")
        assert saved == {k: v for k, v in original.items() if k != "members"}


def test_no_free_search_capacity_skips_paid_planning_and_still_answers(
    client, app, monkeypatch
):
    r, initial, physical, searches, extracts = collective_setup(
        client, app, monkeypatch
    )

    def exhausted():
        raise DomainError("Confirmed free allowance unavailable", 402)

    monkeypatch.setattr(r.tools.provider, "allowance", exhausted)
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert len(physical) == 10 and not searches and not extracts
    assert view["collective_research"]["state"] == "limited"


@pytest.mark.parametrize("turn_off", [False, True])
def test_pause_and_resume_keeps_completed_plans_and_never_repeats_their_charges(
    client, app, monkeypatch, turn_off
):
    r, initial, physical, searches, extracts = collective_setup(
        client, app, monkeypatch
    )
    original_search = r.tools.provider.search
    lock, paused = threading.Lock(), []
    cid = initial["chat"]["id"]

    def pause_once(**args):
        with lock:
            if not paused:
                response = client.post(
                    f"/api/chats/{cid}/control",
                    headers={"Idempotency-Key": str(uuid4())},
                    json={"action": "pause"},
                )
                assert response.is_success, response.text
                paused.append(True)
        return original_search(**args)

    monkeypatch.setattr(r.tools.provider, "search", pause_once)
    drain(app)
    before = client.get("/api/chats/" + cid).json()
    assert before["chat"]["status"] == "paused", before["chat"].get("error")
    assert len(physical) == 3 and not extracts
    previous_searches = len(searches)
    if turn_off:
        changed = client.post(
            f"/api/chats/{cid}/research/settings",
            headers={"Idempotency-Key": str(uuid4())},
            json={"enabled": False},
        )
        assert changed.is_success, changed.text
    response = client.post(
        f"/api/chats/{cid}/control",
        headers={"Idempotency-Key": str(uuid4())},
        json={"action": "resume"},
    )
    assert response.is_success, response.text
    drain(app)
    after = client.get("/api/chats/" + cid).json()
    assert after["chat"]["status"] == "completed", after["chat"].get("error")
    assert (
        len(physical) == 13
        and sum(p["phase"] == "research_plan" for p in physical) == 3
    )
    if turn_off:
        assert len(searches) == previous_searches and not extracts
    else:
        assert len(extracts) == 1
    packets = [p for p in after["context_packs"] if p["namespace"]["role"] == "opening"]
    assert len({p["snapshot_id"] for p in packets}) == 1


def test_extract_batch_is_basic_and_conservatively_admits_six_pages_for_two_credits(
    client, app, monkeypatch
):
    import httpx

    from zerowall.search_providers import TavilyBasic

    original = httpx.Client
    r, initial, _, _, _ = collective_setup(client, app, monkeypatch)
    requests = []

    def handler(request):
        import json

        body = json.loads(request.content)
        requests.append((str(request.url), body))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": url,
                        "raw_content": "Full extracted text with explicit qualifications.",
                    }
                    for url in body["urls"]
                ],
                "failed_results": [],
                "usage": {"credits": 1.2},
            },
        )

    monkeypatch.setattr(
        "zerowall.search_providers.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(r.tools.provider, "extract", TavilyBasic(r.settings).extract)
    result = r.tools.execute(
        initial["chat"],
        {
            "name": "web_extract",
            "arguments": {"urls": [f"https://example.com/a{i}" for i in range(6)]},
        },
        seat="collective_library",
        step_key="batch-six-test",
    )
    assert len(result["versions"]) == 6 and result["reserved_credits"] == 2
    assert requests[0][0] == "https://api.tavily.com/extract"
    assert (
        requests[0][1]["extract_depth"] == "basic"
        and requests[0][1]["format"] == "markdown"
    )
    assert all(v["coverage"] == "provider_extracted_text" for v in result["versions"])
    with r.store.tx() as c:
        assert not r.store.list(c, "source_read", initial["chat"]["mission_id"])
        assert (
            r.store.list(c, "search_credit", initial["chat"]["mission_id"])[0]["amount"]
            == 2
        )


def test_extract_rejects_private_destinations_before_external_dispatch(
    client, app, monkeypatch
):
    r, initial, _, _, extracts = collective_setup(client, app, monkeypatch)
    monkeypatch.setattr("zerowall.web_fetch.public_addresses", real_public_addresses)
    with pytest.raises(DomainError, match="Private, local"):
        r.tools.execute(
            initial["chat"],
            {
                "name": "web_extract",
                "arguments": {"urls": ["http://127.0.0.1/private"]},
            },
            seat="collective_library",
        )
    assert not extracts


def test_common_packet_selects_a_relevant_page_passage_instead_of_navigation(
    client, app, monkeypatch
):
    r, initial, _, _, _ = collective_setup(client, app, monkeypatch)
    chat = initial["chat"]
    page = r.library.ingest(
        chat,
        (
            "Unrelated navigation menu.\n" * 400
            + "Photonic entropy constraints and their thermodynamic qualifications.\n"
        ).encode(),
        title="A long extracted page",
        url="https://example.com/long",
        metadata={"retrieval_method": "tavily_extract_basic", "origin": "public_url"},
    )
    with r.store.tx() as c:
        frozen = r.library.snapshot(c, chat, "relevant-common-passage")
        turn = initial["next_turn"]
        prompt, _ = r.chat.prompt(chat, r.chat.messages(c, chat), turn, c)
        _, prefix, packet = r.context_packs.compile(
            c,
            chat,
            turn,
            prompt,
            frozen,
            search_versions=[page["id"]],
            collective=True,
            retrieval_query="photonic entropy thermodynamic constraints",
        )
        assert "Photonic entropy constraints" in prefix
        assert packet["passages"][0]["line_start"] > 1
