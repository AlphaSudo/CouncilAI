"""A reasoning-only failure can be excluded explicitly without discarding the chat."""

import json

import httpx

from test_council_chat import drain
from test_output_recovery import failed_opening
from test_thinking_and_multiturn import post, token_chat

GLM = "zai-org/GLM-5.3-Flash"


def test_three_model_council_can_finish_without_retrying_reasoning_only_glm(client, app, monkeypatch):
    research, created = token_chat(client, app, budget_usd=24, spending_scope="shared_existing_credit")
    cid, mid = created["chat"]["id"], created["chat"]["mission_id"]
    original, requests = httpx.Client, []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        with research.store.tx() as c:
            chat = research.store.get(c, cid, "chat")
            messages = research.chat.messages(c, chat)
            turn = research.chat.next_turn(chat, messages, c)
            failed = body["model"] == GLM
            text = "" if failed else "A distinct engineering proposal with clear assumptions." if turn["phase"] == "opening" else research.chat.review.demo(c, chat, messages, turn)
        return httpx.Response(200, json={
            "model": body["model"],
            "choices": [{"finish_reason": "length" if failed else "stop", "message": {"content": text}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 12000 if failed else 80, "completion_tokens_details": {"reasoning_tokens": 12000 if failed else 20}},
        })

    monkeypatch.setattr("zerowall.provider.httpx.Client", lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)))
    assert app.state.executor.run_once()
    assert app.state.executor.run_once()
    before = client.get(f"/api/chats/{cid}").json()
    quote = before["model_recovery"]
    assert before["chat"]["status"] == "failed"
    assert quote["allowed"] and quote["failure_kind"] == "reasoning_only_output_limit"
    assert not quote["unknown_charge_retained"] and quote["additional_allowance_usd"] == 0
    assert len(quote["remaining_models"]) == 2
    with research.store.tx() as c:
        money = [tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY rowid")]
        calls = research.store.list(c, "call", mid)
    continued = post(client, f"/api/chats/{cid}/control", {
        "action": "continue_without_model", "recovery_call_id": quote["call_id"],
        "additional_allowance_usd": 0,
    }, "continue-without-reasoning-only-glm")
    assert len(requests) == 2
    with research.store.tx() as c:
        assert [tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY rowid")] == money
        assert research.store.list(c, "call", mid) == calls
    assert continued["messages"][:len(before["messages"])] == before["messages"]
    drain(app)
    finished = client.get(f"/api/chats/{cid}").json()
    assert finished["chat"]["status"] == "completed", finished["chat"].get("error")
    assert finished["messages"][-1]["partial"]
    assert sum(request["model"] == GLM for request in requests) == 1
    assert len(finished["active_members"]) == 2
    assert finished["budget"]["absolute_cap_usd"] == 24


def test_a_saved_public_draft_is_not_offered_as_a_reasoning_only_failure(client, app, monkeypatch):
    research, view, requests = failed_opening(client, app, monkeypatch, draft="A useful partial public answer.", reasoning=11900)
    assert view["output_recovery"]["has_saved_answer"]
    assert view["model_recovery"] is None
