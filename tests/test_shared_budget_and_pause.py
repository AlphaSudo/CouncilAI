"""Shared aggregate credit and pause at a completed provider response boundary."""

import json

import httpx
import pytest

from test_thinking_and_multiturn import post, token_chat
from zerowall.contracts import ChatControl
from zerowall.db import DomainError


def test_shared_credit_adoption_preserves_frozen_brief_holds_and_jobs(client, app):
    research, value = token_chat(client, app, budget_usd=0.25, defer_start=True)
    cid, mid = value["chat"]["id"], value["chat"]["mission_id"]
    with research.store.tx() as c:
        c.execute("INSERT INTO reservations VALUES(?,?,?,?,?,?,?)", ("unknown-current", mid, "unknown-current-call", 236500, None, "unknown", '{}'))
        c.execute("INSERT INTO reservations VALUES(?,?,?,?,?,?,?)", ("known-current", mid, "known-current-call", 20000, 11053, "settled", '{}'))
        c.execute("INSERT INTO reservations VALUES(?,?,?,?,?,?,?)", ("other-chat-hold", "other-mission", "other-call", 1000000, None, "unknown", '{}'))
        money = [tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY rowid")]
        jobs = [tuple(row) for row in c.execute("SELECT * FROM jobs ORDER BY rowid")]
        brief = research.store.get(c, mid, "mission")["brief"]
    before = client.get(f"/api/chats/{cid}").json()
    assert before["conversation_allowance"]["remaining_usd"] == 0.002447
    result = post(client, f"/api/chats/{cid}/spending", {"scope": "shared_existing_credit"}, "share-credit")
    assert result["scope"] == "shared_existing_credit"
    assert result["cap_usd"] == 24
    assert result["remaining_usd"] == pytest.approx(22.752447)
    post(client, f"/api/chats/{cid}/spending", {"scope": "shared_existing_credit"}, "share-again")
    with research.store.tx() as c:
        assert research.store.get(c, mid, "mission")["brief"] == brief
        assert [tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY rowid")] == money
        assert [tuple(row) for row in c.execute("SELECT * FROM jobs ORDER BY rowid")] == jobs
        assert c.execute("SELECT COUNT(*) FROM events WHERE type='budget.shared_cap_adopted'").fetchone()[0] == 1
        assert research.store.get(c, cid, "chat")["status"] == before["chat"]["status"]


def test_new_shared_councils_retain_the_24_dollar_aggregate_guard(client, app):
    research, value = token_chat(client, app, budget_usd=24, spending_scope="shared_existing_credit", defer_start=True)
    mid = value["chat"]["mission_id"]
    assert value["conversation_allowance"]["scope"] == "shared_existing_credit"
    with research.store.tx() as c:
        c.execute("INSERT INTO reservations VALUES(?,?,?,?,?,?,?)", ("aggregate-held", "another-mission", "aggregate-call", 23999999, None, "unknown", '{}'))
        assert research.council_preferences.allowance(c, value["chat"])["remaining_usd"] == 0.000001
        with pytest.raises(DomainError, match="Aggregate credit stop"):
            research.budget.reserve(c, mid, research.settings.models[0], 1000, 1000, "must-not-dispatch")
        assert research.budget.summary(c)["absolute_cap_usd"] == 24
        assert c.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 1


@pytest.mark.parametrize("action", ["pause", "stop", "pause_resume"])
def test_pause_finishes_only_the_dispatched_request_and_stop_still_cancels(client, app, monkeypatch, action):
    research, value = token_chat(client, app, budget_usd=24, spending_scope="shared_existing_credit", review_protocol="reviewed_v4")
    cid, mid = value["chat"]["id"], value["chat"]["mission_id"]
    original = httpx.Client
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        with research.store.tx() as c:
            research.chat.control(c, cid, ChatControl(action="stop" if action == "stop" else "pause"))
            if action == "pause_resume":
                research.chat.control(c, cid, ChatControl(action="resume"))
        events = [
            {"model": body["model"], "choices": [{"index": 0, "delta": {"reasoning_content": "private reasoning"}}]},
            {"model": body["model"], "choices": [{"index": 0, "delta": {"content": "A complete independent answer with clear assumptions."}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 100, "completion_tokens": 50, "completion_tokens_details": {"reasoning_tokens": 25}}},
        ]
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content="".join("data: " + json.dumps(event) + "\n\n" for event in events) + "data: [DONE]\n\n")

    monkeypatch.setattr("zerowall.provider.httpx.Client", lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)))
    assert app.state.executor.run_once()
    current = client.get(f"/api/chats/{cid}").json()
    assert len(requests) == 1
    with research.store.tx() as c:
        calls = research.store.list(c, "call", mid)
        assert len(calls) == 1
        reservation = c.execute("SELECT * FROM reservations WHERE mission_id=?", (mid,)).fetchone()
        if action == "stop":
            assert current["chat"]["status"] == "cancelled"
            assert calls[0]["state"] == "unknown" and reservation["state"] == "unknown"
        else:
            assert calls[0]["state"] == "completed" and reservation["state"] == "settled"
            assert reservation["actual_microusd"] < reservation["maximum_microusd"]
            assert len([message for message in current["messages"] if message["role"] == "assistant"]) == 1
            assert current["chat"]["status"] == ("running" if action == "pause_resume" else "paused")
        assert current["chat"]["active_turn"] is None
    if action != "pause_resume":
        assert not app.state.executor.run_once()


def test_recovery_reports_amended_shared_scope_instead_of_the_frozen_quarter_dollar_cap(client, app, monkeypatch):
    from test_output_recovery import failed_opening
    research, current, requests = failed_opening(client, app, monkeypatch)
    cid = current["chat"]["id"]
    with research.store.tx() as c:
        mission = research.store.get(c, current["chat"]["mission_id"], "mission")
        mission["brief"]["budget_usd"] = 0.25
        research.store.put(c, "mission", mission)
    post(client, f"/api/chats/{cid}/spending", {"scope": "shared_existing_credit"}, "recovery-shared")
    result = client.get(f"/api/chats/{cid}").json()["output_recovery"]
    assert result["spending_scope"] == "shared_existing_credit"
    assert result["conversation_remaining_usd"] == result["global_remaining_usd"]
    assert result["available"]
