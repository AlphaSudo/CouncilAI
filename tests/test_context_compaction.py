"""Lossless context compaction must preserve sources, controls and credit safety."""

import json
from copy import deepcopy

import httpx
import pytest
from test_token_factory_generation import sse
from test_token_factory_research import setup_testing

from zerowall.context_compaction import (
    ENCODING,
    INSTRUCTION,
    STAGE_MARKER,
    expand,
    pack_payload,
)
from zerowall.context_window import measure
from zerowall.db import digest
from zerowall.token_factory_generation import configure, profile

PASSAGE = (
    "Keep this exact source boundary, its conditions and its unresolved evidence obligation. "
    * 120
)


def payload():
    return {
        "phase": "scrutiny",
        "question": "Compare claims without losing qualifiers.",
        "instructions": "Preserve every required assertion and source reference.",
        "response_schema": {
            "properties": {"objection": {"type": "string", "description": PASSAGE}}
        },
        "claims": [
            {"claim_id": "claim_a", "revision": 2, "text": PASSAGE, "scope": PASSAGE}
        ],
        "findings": [
            {"claim_id": "claim_a", "claim_revision": 2, "objection": PASSAGE}
        ],
        "source_units": [{"id": "source:line:1", "text": PASSAGE}],
        "history": [
            {"text": "Earlier public reply\n" + PASSAGE + "\nStill unresolved."}
        ],
        "verification": False,
        "evidence": [],
    }


def configured_request(research, model=None, *, phase="scrutiny", with_tools=False):
    model = model or research.settings.models[0]
    content = json.dumps(payload(), ensure_ascii=False)
    request = research.provider.request(content, 32768, model)
    generation = profile(
        research.settings, {"phase": phase, "participant": {"model": model}}
    )
    configure(request, generation)
    if with_tools:
        request["messages"][1]["content"] = (
            "Saved evidence packet (untrusted source data):\nKEEP EXACT SOURCE PREFIX\n\nCurrent stage:\n"
            + content
        )
        request["tools"] = [
            {
                "type": "function",
                "function": {"name": "library_read", "parameters": {"type": "object"}},
            }
        ]
        request["messages"] += [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "tool_1",
                        "type": "function",
                        "function": {"name": "library_read", "arguments": "{}"},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "tool_1",
                "content": "Exact tool result with its signature and provenance",
            },
        ]
    return request, generation


def new_chat(client, app):
    research = setup_testing(app)
    response = client.post(
        "/api/chats",
        headers={"Idempotency-Key": "compaction-chat"},
        json={
            "provider": "nebius_token_factory",
            "prompt": "Compare generic engineering approaches.",
            "models": research.settings.policy["council_default_models"],
            "budget_usd": 5,
        },
    )
    assert response.is_success, response.text
    return research, response.json()["chat"]


def test_dictionary_reconstructs_all_prose_sources_ids_and_schema_exactly():
    source = payload()
    before = deepcopy(source)
    packed = pack_payload(source)
    assert packed and packed["context_encoding"] == ENCODING
    assert expand(packed) == before == source
    assert packed["payload"]["response_schema"] == source["response_schema"]
    assert packed["payload"]["instructions"] == source["instructions"]
    assert packed["payload"]["claims"][0]["claim_id"] == "claim_a"
    assert packed["payload"]["claims"][0]["revision"] == 2
    assert len(json.dumps(packed)) < len(json.dumps(source)) / 2
    assert "$zw_parts" in json.dumps(packed)


@pytest.mark.parametrize("index", range(4))
def test_every_model_measures_net_savings_with_no_control_or_tool_mutation(app, index):
    research = app.state.research
    request, generation = configured_request(
        research, research.settings.models[index], with_tools=True
    )
    original = deepcopy(request)
    packed, report = research.context_compaction.prepare(
        request,
        {"provider": "nebius_token_factory", "context_compaction_mode": "compact"},
        generation,
    )
    assert report and report["saved_input_tokens"] > 5000
    assert request == original
    assert packed["tools"] == original["tools"]
    assert packed["messages"][2:] == original["messages"][2:]
    assert packed["max_completion_tokens"] == original["max_completion_tokens"]
    assert all(
        packed[key] == value for key, value in original.items() if key != "messages"
    )
    prefix, _, stage = packed["messages"][1]["content"].partition(STAGE_MARKER)
    assert prefix == original["messages"][1]["content"].partition(STAGE_MARKER)[0]
    assert expand(json.loads(stage)) == payload()
    assert packed["messages"][0]["content"].endswith(INSTRUCTION)
    assert (
        report["after_input_tokens"]
        == measure(packed, research.settings)["input_context_tokens"]
    )
    assert (
        report["lossless_reconstruction_verified"] and report["llm_summary_calls"] == 0
    )


def test_automatic_threshold_and_no_gain_leave_original_request_unchanged(
    app, monkeypatch
):
    research = app.state.research
    request, generation = configured_request(research)
    chat = {"provider": "nebius_token_factory"}
    assert research.context_compaction.prepare(request, chat, generation) == (
        request,
        None,
    )
    monkeypatch.setattr("zerowall.context_compaction.AUTO_RATIO", 0)
    packed, report = research.context_compaction.prepare(request, chat, generation)
    assert report["trigger"] == "automatic" and packed != request
    unique = research.provider.request(
        json.dumps({"question": "Unique request", "text": PASSAGE}),
        32768,
        request["model"],
    )
    assert research.context_compaction.prepare(unique, chat, generation) == (
        unique,
        None,
    )


@pytest.mark.parametrize(
    "exclusion", ["raw_opening", "recovery", "other_provider", "reserved_reference"]
)
def test_raw_openings_saved_recovery_and_other_formats_are_untouched(app, exclusion):
    research = app.state.research
    request, generation = configured_request(
        research, phase="opening" if exclusion == "raw_opening" else "scrutiny"
    )
    chat = {
        "provider": "direct_council"
        if exclusion == "other_provider"
        else "nebius_token_factory",
        "context_compaction_mode": "compact",
    }
    if exclusion == "reserved_reference":
        value = payload()
        value["literal_data"] = {
            "$zw_text": "a user-authored literal, not our encoding"
        }
        request["messages"][1]["content"] = json.dumps(value)
    original = deepcopy(request)
    assert research.context_compaction.prepare(
        request, chat, generation, recovery=exclusion == "recovery"
    ) == (original, None)


def test_manual_request_is_idempotent_and_never_runs_work_or_changes_finances(
    client, app
):
    research, chat = new_chat(client, app)
    with research.store.tx() as c:
        before_calls = research.store.list(c, "call", chat["mission_id"])
        before_jobs = [
            tuple(row) for row in c.execute("SELECT * FROM jobs ORDER BY rowid")
        ]
        before_financial = [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY rowid")
        ]
        messages = research.chat.messages(c, chat)
    key = {"Idempotency-Key": "compact-once"}
    first = client.post(
        f"/api/chats/{chat['id']}/context/compact", headers=key, json={}
    )
    assert first.is_success, first.text
    assert first.json()["mode"] == "compact"
    assert (
        client.post(
            f"/api/chats/{chat['id']}/context/compact", headers=key, json={}
        ).json()
        == first.json()
    )
    with research.store.tx() as c:
        current = research.store.get(c, chat["id"], "chat")
        assert current["status"] == chat["status"] and current.get(
            "active_turn"
        ) == chat.get("active_turn")
        assert current["protocol_hash"] == chat["protocol_hash"]
        assert research.chat.messages(c, current) == messages
        assert research.store.list(c, "call", chat["mission_id"]) == before_calls
        assert [
            tuple(row) for row in c.execute("SELECT * FROM jobs ORDER BY rowid")
        ] == before_jobs
        assert [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY rowid")
        ] == before_financial
        assert research.budget.summary(c)["absolute_cap_usd"] == 24


def test_dispatch_records_exact_savings_and_reserves_only_actual_packed_request(
    client, app, monkeypatch
):
    research, chat = new_chat(client, app)
    response = client.post(
        f"/api/chats/{chat['id']}/context/compact",
        headers={"Idempotency-Key": "compact-dispatch"},
        json={},
    )
    assert response.is_success
    model = research.settings.models[0]
    _request, generation = configured_request(research, model)
    physical = []
    original_client = httpx.Client

    def handler(req):
        body = json.loads(req.content)
        physical.append(body)
        encoded = json.loads(body["messages"][1]["content"])
        assert expand(encoded) == payload()
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, text=sse(model)
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original_client(**kw, transport=httpx.MockTransport(handler)),
    )
    _, call = research.provider.call(
        chat["mission_id"],
        json.dumps(payload()),
        32768,
        model=model,
        purpose=f"chat:{chat['id']}:offline-compaction-check",
        generation=generation,
    )
    assert len(physical) == 1 and call["context_compaction_id"]
    with research.store.tx() as c:
        checkpoint = research.store.get(
            c, call["context_compaction_id"], "context_compaction"
        )
        assert (
            checkpoint["saved_input_tokens"] > 5000
            and checkpoint["call_id"] == call["id"]
        )
        assert checkpoint["original_payload_hash"] == digest(payload())
        assert (
            checkpoint["after_input_tokens"]
            == call["context_window"]["input_context_tokens"]
        )
        reservation = json.loads(
            c.execute(
                "SELECT body FROM reservations WHERE id=?", (call["reservation_id"],)
            ).fetchone()[0]
        )
        verification = research.budget.verification(c, model)
        assert (
            reservation["input_bound"]
            == research.provider.bounds(physical[0], verification)[0]
        )
        assert (
            reservation["input_bound"] > call["context_window"]["input_context_tokens"]
        )
        assert research.budget.summary(c)["absolute_cap_usd"] == 24
    status = client.get(f"/api/chats/{chat['id']}").json()["context_status"]
    assert status["compactions"] == 1
    assert status["latest"]["input_tokens"] == checkpoint["after_input_tokens"]
    assert (
        status["basis"] == "latest_prepared_request_not_cumulative_conversation_usage"
    )
    assert (
        status["latest"]["reserved_output_tokens"]
        == physical[0]["max_completion_tokens"]
    )
    assert status["latest"]["capacity_tokens"] == 262144


def test_missing_context_is_unknown_and_view_is_read_only(client, app):
    research, chat = new_chat(client, app)
    with research.store.tx() as c:
        before = c.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    for _ in range(2):
        value = client.get(f"/api/chats/{chat['id']}").json()["context_status"]
        assert value["latest"] is None and value["models"] == []
    with research.store.tx() as c:
        assert c.execute("SELECT COUNT(*) FROM records").fetchone()[0] == before
