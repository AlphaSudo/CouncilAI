"""Final-payload admission, without dropping protected source content."""

import json

import httpx
import pytest
from test_council_chat import drain
from test_token_factory_generation import sse
from test_token_factory_research import setup_testing
from test_unified_council import create

from zerowall.council_review_v1 import CouncilReview as LegacyReview
from zerowall.db import DomainError


def long_answer(author):
    return "\n".join(
        f"Approach {author}.{index}: compare explicit assumptions, measurable constraints, and remaining evidence gaps."
        for index in range(90)
    )


def test_current_review_checks_final_context_not_duplicated_legacy_payload(client, app):
    initial = create(client)
    for _ in range(3):
        assert app.state.executor.run_once()
    research = app.state.research
    with research.store.tx() as c:
        chat = research.store.get(c, initial["chat"]["id"], "chat")
        messages = research.chat.messages(c, chat)
        openings = [message for message in messages if message["phase"] == "opening"]
        for index, message in enumerate(openings):
            message["content"] = long_answer(index)
            research.store.put(c, "chat_message", message)
        turn = research.chat.next_turn(chat, messages, c)
        engine = research.chat.review.engine(chat)
        intermediate, _ = LegacyReview.prompt(engine, c, chat, messages, turn)
        assert len(intermediate.encode()) > 90000
        actual, context_ids = research.chat.prompt(chat, messages, turn, c)
        assert len(actual.encode()) <= 90000
        payload = json.loads(actual)
        expected = [
            unit for message in openings for unit in engine.source_units(message)
        ]
        assert payload["source_units"] == [
            {key: value for key, value in unit.items() if key not in ("start", "end")}
            for unit in expected
        ]
        assert payload["required_source_message_ids"] == [m["id"] for m in openings]
        assert all(message["id"] in context_ids for message in openings)
        assert len(payload["source_units"]) == 270
        # The canonical local source map still retains precise character offsets.
        assert all("start" in unit and "end" in unit for unit in expected)


def test_truly_oversized_final_review_reports_application_bytes_without_dropping_notes(
    client, app
):
    initial = create(client)
    drain(app)
    research = app.state.research
    with research.store.tx() as c:
        chat = research.store.get(c, initial["chat"]["id"], "chat")
        record = research.chat.review.record(c, chat)
        notes = []
        for index in range(15):
            notes.append(
                research.chat.message(
                    c,
                    chat,
                    role="user",
                    content=f"Required concern {index}: "
                    + "explicit evidence limits " * 400,
                    phase="intervention",
                    review_cycle=record["cycle"],
                )
            )
        turn = research.chat.review.schedule(chat, record)[-1]
        with pytest.raises(
            DomainError, match="application's 90,000-byte review-packing limit"
        ):
            research.chat.prompt(chat, research.chat.messages(c, chat), turn, c)
        current = research.chat.messages(c, chat)
        assert all(note in current for note in notes)
        assert not research.store.list(c, "call", chat["mission_id"])


def test_long_token_factory_openings_reach_extraction_with_every_source_unit(
    client, app, monkeypatch
):
    research = setup_testing(app)
    original, requests = httpx.Client, []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) <= 3:
            text = "\n".join([long_answer(len(requests))] * 3)
        else:
            stage = body["messages"][-1]["content"].split("\n\nCurrent stage:\n", 1)[-1]
            payload = json.loads(stage)
            assert payload["phase"] == "extraction"
            assert len(payload["source_units"]) == 810
            assert len(payload["required_source_message_ids"]) == 3
            assert len(request.content) > 120000
            with research.store.tx() as c:
                chat = research.store.get(c, cid, "chat")
                turn = research.chat.next_turn(chat, research.chat.messages(c, chat), c)
                text = research.chat.review.demo(
                    c, chat, research.chat.messages(c, chat), turn
                )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=sse(body["model"], text=text),
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    response = client.post(
        "/api/chats",
        headers={"Idempotency-Key": "long-openings"},
        json={
            "prompt": "Compare generic engineering approaches with explicit assumptions.",
            "provider": "nebius_token_factory",
            "models": research.settings.policy["council_default_models"],
            "budget_usd": 1,
            "research_tools": True,
        },
    )
    assert response.is_success, response.text
    cid = response.json()["chat"]["id"]
    research.library.ingest(
        response.json()["chat"],
        b"Compare engineering approaches only within their stated assumptions and evidence limits.",
        title="Common engineering requirements",
    )
    for _ in range(4):
        assert app.state.executor.run_once()
    current = client.get("/api/chats/" + cid).json()
    assert current["chat"]["status"] == "running", current["chat"].get("error")
    assert current["messages"][-1]["phase"] == "extraction"
    assert len(requests) == 4
    assert current["budget"]["absolute_cap_usd"] == 24
    with research.store.tx() as c:
        packs = research.store.list(c, "context_pack", current["chat"]["mission_id"])
        assert any(pack["request_bytes"] > 100000 for pack in packs)
        calls = research.store.list(c, "call", current["chat"]["mission_id"])
        assert calls[-1]["context_window"]["context_tokens"] == 262144
