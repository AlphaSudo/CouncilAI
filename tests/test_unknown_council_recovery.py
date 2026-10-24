"""Interrupted transport is recoverable without automatic dispatch or fake completion."""

from copy import deepcopy

import pytest
from test_answer_first_provider import setup
from test_council_chat import drain

from zerowall.answer_delivery import AnswerDelivery


@pytest.mark.parametrize("mode", ["first_unknown", "unknown"])
def test_explicit_retry_preserves_prior_replies_and_the_unknown_reservation(
    client, app, monkeypatch, mode
):
    r, cid, physical = setup(client, app, monkeypatch, mode)
    drain(app)
    before = client.get("/api/chats/" + cid).json()
    assert before["chat"]["status"] == "paused"
    recovery = before["chat"]["pending_request_recovery"]
    with r.store.tx() as c:
        old = deepcopy(r.store.get(c, recovery["call_id"], "call"))
        reservation = tuple(
            c.execute(
                "SELECT * FROM reservations WHERE id=?", (old["reservation_id"],)
            ).fetchone()
        )
    count = len(physical)
    denied = client.post(
        "/api/chats/" + cid + "/control",
        headers={"Idempotency-Key": "unacknowledged-retry"},
        json={"action": "resume"},
    )
    assert (
        not denied.is_success
        and "unknown charge" in denied.text
        and len(physical) == count
    )
    accepted = client.post(
        "/api/chats/" + cid + "/control",
        headers={"Idempotency-Key": "acknowledged-retry"},
        json={"action": "resume", "authorize_retry_with_unknown_charge": True},
    )
    assert accepted.is_success, accepted.text
    drain(app)
    after = client.get("/api/chats/" + cid).json()
    assert after["chat"]["status"] == "completed", after["chat"].get("error")
    assert not after["chat"].get("pending_request_recovery")
    assert after["messages"][: len(before["messages"])] == before["messages"]
    assert len([m for m in after["messages"] if m["phase"] == "opening"]) == 3
    assert (
        len(physical) > count
        and after["budget"]["unknown_usd"] == before["budget"]["unknown_usd"]
    )
    with r.store.tx() as c:
        assert r.store.get(c, old["id"], "call") == old
        assert (
            tuple(
                c.execute(
                    "SELECT * FROM reservations WHERE id=?", (old["reservation_id"],)
                ).fetchone()
            )
            == reservation
        )
    assert not app.state.executor.run_once()


def test_explicit_continue_without_failed_model_works_in_current_protocol(
    client, app, monkeypatch
):
    _r, cid, physical = setup(client, app, monkeypatch, "first_unknown")
    drain(app)
    before = client.get("/api/chats/" + cid).json()
    quote = before["model_recovery"]
    assert quote and quote["allowed"] and quote["unknown_charge_retained"]
    result = client.post(
        "/api/chats/" + cid + "/control",
        headers={"Idempotency-Key": "explicitly-skip-failed-model"},
        json={
            "action": "continue_without_model",
            "recovery_call_id": quote["call_id"],
            "additional_allowance_usd": quote["additional_allowance_usd"],
            "authorize_retry_with_unknown_charge": True,
        },
    )
    assert result.is_success, result.text
    drain(app)
    after = client.get("/api/chats/" + cid).json()
    assert after["chat"]["status"] == "completed", after["chat"].get("error")
    assert len([m for m in after["messages"] if m["phase"] == "opening"]) == 2
    assert quote["member_id"] in after["chat"]["unavailable_members"]
    assert after["budget"]["unknown_usd"] == before["budget"]["unknown_usd"]
    assert sum(p["model"] == quote["model"] for p in physical) == 1


def test_old_empty_completion_is_reopened_locally_once_without_changing_messages_or_money(
    client, app, monkeypatch
):
    r, cid, physical = setup(client, app, monkeypatch, "first_unknown")
    drain(app)
    with r.store.tx() as c:
        chat = r.store.get(c, cid, "chat")
        notice = r.chat.message(
            c,
            chat,
            role="system",
            phase="synthesis",
            round=1,
            review_cycle=chat["review_cycle"],
            name="Saved council responses",
            source="local_partial",
            content="No public model answer was received. Earlier empty-final bug fixture.",
            generation_state="unavailable",
        )
        chat.update(
            status="completed",
            final_message_id=notice["id"],
            completion_reason="provider_or_action_boundary",
        )
        chat.pop("pending_request_recovery")
        r.store.put(c, "chat", chat)
        messages = deepcopy(r.chat.messages(c, chat))
        calls = deepcopy(r.store.list(c, "call", chat["mission_id"]))
        money = [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY id")
        ]
    delivery = AnswerDelivery(r.chat)
    assert delivery.reopen_empty_unknown_boundaries() == 1
    assert delivery.reopen_empty_unknown_boundaries() == 0
    view = client.get("/api/chats/" + cid).json()
    assert (
        view["chat"]["status"] == "paused" and view["chat"]["final_message_id"] is None
    )
    with r.store.tx() as c:
        # The API adds presentation metadata; compare immutable stored records
        # to the stored baseline rather than comparing two different shapes.
        assert r.chat.messages(c, r.store.get(c, cid, "chat")) == messages
        assert r.store.list(c, "call", chat["mission_id"]) == calls
        assert [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY id")
        ] == money
    assert len(physical) == 1 and not app.state.executor.run_once()
