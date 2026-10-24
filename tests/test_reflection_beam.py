"""Beam defaults, public-context continuations and audited same-chat replacement."""

import json
from copy import deepcopy

import httpx
import pytest

from test_council_chat import drain
from test_token_factory_research import setup_testing
from zerowall.beam_request import public_context_request
from zerowall.db import DomainError, digest
from zerowall.token_factory_generation import configure, profile

BEAM = "reflection/beam"
GLM = "zai-org/GLM-5.3-Flash"


def test_beam_is_the_default_seat_and_retired_glm_stays_historical(client, app):
    r = setup_testing(app, include_beam=True)
    data = client.get("/api/chats/bootstrap").json()["providers"]["nebius_token_factory"]
    assert data["default_models"] == [r.settings.models[i] for i in (0, 1, 3)]
    assert BEAM in data["default_models"] and GLM not in data["default_models"]
    assert BEAM in [m["id"] for m in data["models"]]
    assert GLM not in [m["id"] for m in data["models"]]
    assert GLM in r.settings.models  # Old receipts and explicitly resumed history remain readable.


@pytest.mark.parametrize("phase,recovery", [("opening", False), ("scrutiny", False), ("repair", False), ("opening", True)])
def test_beam_4k_target_keeps_thinking_on_and_completion_room_separate(app, phase, recovery):
    r = app.state.research
    generation = profile(r.settings, {"phase": phase, "participant": {"model": BEAM}}, recovery=recovery)
    request = r.provider.request("An unchanged public question.", 16384, BEAM)
    configure(request, generation)
    assert request["reasoning_effort"] == "low"
    assert request["max_completion_tokens"] == 16384
    assert generation["reasoning_budget_tokens"] == 4000
    assert generation["client_reasoning_stop_enabled"] is False
    assert "4,000 reasoning tokens" in request["messages"][0]["content"]
    assert "thinking_token_budget" not in request and "chat_template_kwargs" not in request
    assert generation["continuation_mode"] == "fresh_public_context"


def test_public_beam_history_is_quoted_without_fabricating_missing_reasoning():
    request = {"model": BEAM, "messages": [
        {"role": "system", "content": "Keep source boundaries."},
        {"role": "user", "content": "The current question and saved evidence."},
        {"role": "assistant", "content": "A saved public draft.", "reasoning_content": "PRIVATE_SENTINEL"},
        {"role": "tool", "content": "Saved source:version_1:L1-L4", "tool_call_id": "tc1"},
        {"role": "user", "content": "Finish the answer using these public sources."},
    ]}
    original = deepcopy(request)
    prepared = public_context_request(request)
    assert request == original
    assert prepared["messages"][:2] == original["messages"][:2]
    assert all(m["role"] in ("system", "user") for m in prepared["messages"])
    assert "PRIVATE_SENTINEL" not in json.dumps(prepared)
    assert "saved public draft" in json.dumps(prepared).lower()
    assert "source:version_1:L1-L4" in json.dumps(prepared)
    assert prepared["messages"][-1] == original["messages"][-1]


def test_saved_glm_seat_can_switch_to_beam_without_rewriting_history_or_retrying(client, app, monkeypatch):
    r = setup_testing(app, include_beam=True)
    response = client.post("/api/chats", headers={"Idempotency-Key": "beam-old-council"}, json={
        "prompt": "Compare generic engineering approaches with explicit assumptions.",
        "provider": "nebius_token_factory", "models": [r.settings.models[0], GLM, r.settings.models[3]],
        "budget_usd": 24, "spending_scope": "shared_existing_credit",
    })
    assert response.is_success, response.text
    cid, mid = response.json()["chat"]["id"], response.json()["chat"]["mission_id"]
    with r.store.tx() as c:
        chat = r.store.get(c, cid, "chat")
        member = next(p for p in chat["participants"] if p["model"] == GLM)
        with pytest.raises(DomainError, match="active request"):
            r.chat.runtime.replace_token_factory_member(c, cid, member["id"], BEAM)
        c.execute("UPDATE jobs SET state='cancelled' WHERE target_id=?", (cid,))
        chat["status"] = "paused"
        r.store.put(c, "chat", chat)
        orphan_call = {"id": "call_beam_orphan_guard", "mission_id": mid,
                       "state": "dispatching", "purpose": f"chat:{cid}:opening"}
        r.store.put(c, "call", orphan_call)
        with pytest.raises(DomainError, match="active request"):
            r.chat.runtime.replace_token_factory_member(c, cid, member["id"], BEAM)
        c.execute("DELETE FROM records WHERE id=?", (orphan_call["id"],))
        historical = r.chat.message(c, chat, role="assistant", content="A previously saved independent engineering proposal with explicit assumptions.",
            name="GLM-5.3-Flash", model=GLM, actual_model=GLM, provider="nebius_token_factory",
            participant_id=member["id"], phase="opening", round=1, review_cycle=1,
            turn_key=f"review:1:opening:{member['id']}", source="model_api")
        protocol_hash, frozen = chat["protocol_hash"], deepcopy(chat["participants"])
        money = [tuple(row) for row in c.execute("SELECT * FROM reservations")]
        before_calls = r.store.list(c, "call", mid)
        before_messages = r.chat.messages(c, chat)
        changed = r.chat.runtime.replace_token_factory_member(c, cid, member["id"], BEAM)
        assert changed["participants"] == frozen and changed["protocol_hash"] == protocol_hash
        assert changed["status"] == "paused"
        assert r.chat.messages(c, changed) == before_messages
        assert r.store.list(c, "call", mid) == before_calls
        assert [tuple(row) for row in c.execute("SELECT * FROM reservations")] == money
        assert r.chat.runtime.effective_member(changed, member)["model"] == BEAM
        effective = r.chat.runtime.effective_member(changed, member)
        assert r.chat.runtime.effective_member(changed, effective) == effective
        assert digest(r.chat.runtime.replace_token_factory_member(c, cid, member["id"], BEAM)) == digest(changed)

    original, requests = httpx.Client, []
    def handler(request):
        body = json.loads(request.content); requests.append(body)
        with r.store.tx() as c:
            chat = r.store.get(c, cid, "chat"); messages = r.chat.messages(c, chat)
            turn = r.chat.next_turn(chat, messages, c)
            content = "A distinct public engineering proposal with stated assumptions." if turn["phase"] == "opening" else r.chat.review.demo(c, chat, messages, turn)
        return httpx.Response(200, json={"model": body["model"], "choices": [{"finish_reason": "stop", "message": {"content": content}}], "usage": {"prompt_tokens": 100, "completion_tokens": 90, "completion_tokens_details": {"reasoning_tokens": 20}}})
    monkeypatch.setattr("zerowall.provider.httpx.Client", lambda **kw: original(**kw, transport=httpx.MockTransport(handler)))
    resumed = client.post(f"/api/chats/{cid}/control", headers={"Idempotency-Key": "resume-beam-seat"}, json={"action": "resume"})
    assert resumed.is_success, resumed.text
    drain(app)
    finished = client.get(f"/api/chats/{cid}").json()
    assert finished["chat"]["status"] == "completed", finished["chat"].get("error")
    assert any(x["model"] == BEAM for x in requests) and all(x["model"] != GLM for x in requests)
    beam_messages = [m for m in finished["messages"] if m.get("model") == BEAM]
    assert beam_messages and all(m["replacement_for"] == GLM for m in beam_messages)
    with r.store.tx() as c:
        # API presentation adds availability flags; compare the immutable saved
        # record to prove replacement did not rewrite the previous model reply.
        assert r.store.get(c, historical["id"], "chat_message") == historical
    assert any(p["model"] == BEAM for p in finished["effective_members"])
    assert next(p for p in finished["thinking"]["models"] if p["model"] == BEAM)["reasoning_budget_tokens"] == 4000
