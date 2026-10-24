"""Offline recovery after a timed-out optional opening; no paid inference."""

import json
import uuid
from copy import deepcopy

import httpx
import pytest
from test_council_chat import drain
from test_token_factory_generation import sse
from test_token_factory_research import setup_testing

from zerowall.budget import mission_cap_micro

LIGHTNING = "nvidia/Nemotron-3_5-Lightning"


def failed_chat(client, app, monkeypatch, seats=4):
    research = setup_testing(app)
    original, requests = httpx.Client, []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if body["model"] == LIGHTNING:
            raise httpx.ReadTimeout("Offline provider timeout")
        with research.store.tx() as c:
            chat = json.loads(
                c.execute(
                    "SELECT body FROM records WHERE kind='chat' ORDER BY rowid DESC LIMIT 1"
                ).fetchone()[0]
            )
            messages = research.chat.messages(c, chat)
            turn = research.chat.next_turn(chat, messages, c)
            if turn["phase"] == "opening":
                text = "A distinct engineering proposal under explicit constraints and evidence limits."
            else:
                text = research.chat.review.demo(c, chat, messages, turn)
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
        headers={"Idempotency-Key": "timed-out-lightning"},
        json={
            "prompt": "Compare generic engineering approaches under explicit constraints.",
            "provider": "nebius_token_factory",
            "review_protocol": "reviewed_v3",
            "models": research.settings.models[:seats],
            "budget_usd": 0.05,
        },
    )
    assert response.is_success, response.text
    cid = response.json()["chat"]["id"]
    for _ in range(3):
        assert app.state.executor.run_once()
    before = client.get("/api/chats/" + cid).json()
    assert before["chat"]["status"] == "failed"
    return research, before, requests


def continue_chat(client, before, **overrides):
    return client.post(
        f"/api/chats/{before['chat']['id']}/control",
        headers={"Idempotency-Key": uuid.uuid4().hex},
        json={
            "action": "continue_without_model",
            "authorize_retry_with_unknown_charge": True,
            "recovery_call_id": before["model_recovery"]["call_id"],
            "additional_allowance_usd": before["model_recovery"][
                "additional_allowance_usd"
            ],
            **overrides,
        },
    )


def test_token_factory_defaults_keep_lightning_available_but_unselected(client, app):
    research = setup_testing(app)
    data = client.get("/api/chats/bootstrap").json()["providers"][
        "nebius_token_factory"
    ]
    assert data["default_models"] == [research.settings.models[i] for i in [0, 1, 3]]
    assert [model["id"] for model in data["models"]] == research.settings.models
    assert (
        "one minute"
        in next(model for model in data["models"] if model["id"] == LIGHTNING)[
            "selection_notice"
        ]
    )
    with research.store.tx() as c:
        assert (
            c.execute("SELECT COUNT(*) FROM records WHERE kind='call'").fetchone()[0]
            == 0
        )


@pytest.mark.parametrize("seats", [3, 4])
def test_continue_same_chat_keeps_unknown_charge_and_answers_and_never_retries_excluded_model(
    client, app, monkeypatch, seats
):
    research, before, requests = failed_chat(client, app, monkeypatch, seats)
    cid, mid = before["chat"]["id"], before["chat"]["mission_id"]
    quote = before["model_recovery"]
    assert quote["allowed"] and quote["additional_allowance_usd"] == 0.25
    assert len(requests) == 3
    with research.store.tx() as c:
        old_calls = deepcopy(research.store.list(c, "call", mid))
        old_reservations = [
            tuple(row)
            for row in c.execute(
                "SELECT * FROM reservations WHERE mission_id=?", (mid,)
            )
        ]
        mission = research.store.get(c, mid, "mission")
        brief, protocol_hash = deepcopy(mission["brief"]), mission["protocol_hash"]
        authority = deepcopy(
            research.store.setting(c, "token_factory_spending_authority")
        )
    response = continue_chat(client, before)
    assert response.is_success, response.text
    updated = response.json()
    duplicate = continue_chat(client, before)
    assert duplicate.status_code == 409  # A second click cannot add allowance twice.
    assert len(requests) == 3  # Enqueue only; no inference in the control request.
    assert updated["chat"]["id"] == cid
    assert updated["messages"][: len(before["messages"])] == before["messages"]
    assert updated["next_turn"]["participant"]["model"] != LIGHTNING
    assert updated["participation_notices"][0]["call_id"] == quote["call_id"]
    assert updated["participation_notices"][0]["phase"] == "opening"
    with research.store.tx() as c:
        assert research.store.list(c, "call", mid) == old_calls
        assert [
            tuple(row)
            for row in c.execute(
                "SELECT * FROM reservations WHERE mission_id=?", (mid,)
            )
        ] == old_reservations
        mission = research.store.get(c, mid, "mission")
        assert mission["brief"] == brief and mission["protocol_hash"] == protocol_hash
        assert mission_cap_micro(mission) == 300000
        assert (
            research.store.setting(c, "token_factory_spending_authority") == authority
        )
    drain(app)
    completed = client.get("/api/chats/" + cid).json()
    assert completed["chat"]["status"] == "completed", completed["chat"].get("error")
    assert completed["messages"][-1]["partial"]
    assert completed["budget"]["unknown_usd"] == before["budget"]["unknown_usd"]
    assert sum(request["model"] == LIGHTNING for request in requests) == 1
    followup = client.post(
        f"/api/chats/{cid}/messages",
        headers={"Idempotency-Key": "continue-without-lightning-followup"},
        json={"text": "Compare the same approaches with a different evaluation goal."},
    )
    assert followup.is_success, followup.text
    drain(app)
    final = client.get("/api/chats/" + cid).json()
    assert final["chat"]["status"] == "completed", final["chat"].get("error")
    assert final["messages"][: len(completed["messages"])] == completed["messages"]
    assert sum(request["model"] == LIGHTNING for request in requests) == 1
    assert final["budget"]["absolute_cap_usd"] == 24


@pytest.mark.parametrize(
    "change",
    [
        {"authorize_retry_with_unknown_charge": False},
        {"additional_allowance_usd": 0},
        {"additional_allowance_usd": 24},
        {"recovery_call_id": "old-or-foreign-call"},
    ],
)
def test_recovery_rejects_missing_acknowledgement_changed_allowance_or_stale_call_atomically(
    client, app, monkeypatch, change
):
    research, before, requests = failed_chat(client, app, monkeypatch)
    with research.store.tx() as c:
        original = [
            tuple(row) for row in c.execute("SELECT * FROM records ORDER BY rowid")
        ]
    response = continue_chat(client, before, **change)
    assert response.status_code == 409, response.text
    assert len(requests) == 3
    with research.store.tx() as c:
        assert [
            tuple(row) for row in c.execute("SELECT * FROM records ORDER BY rowid")
        ] == original


def test_recovery_cannot_enlarge_aggregate_authority(client, app, monkeypatch):
    research, before, requests = failed_chat(client, app, monkeypatch)
    with research.store.tx() as c:
        verification = research.store.setting(c, "live_verification")
        verification["operational_cap_usd"] = 0.1
        research.store.set_setting(c, "live_verification", verification)
    current = client.get("/api/chats/" + before["chat"]["id"]).json()
    assert not current["model_recovery"]["allowed"]
    response = continue_chat(client, current)
    assert response.status_code == 402
    assert len(requests) == 3


def test_allowance_cannot_be_added_through_normal_resume(client):
    response = client.post(
        "/api/chats/nonexistent/control",
        json={"action": "resume", "additional_allowance_usd": 0.25},
    )
    assert response.status_code == 422
