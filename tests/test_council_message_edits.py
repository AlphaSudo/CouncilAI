"""Revising a question never rewrites history, replays old intent or refunds calls."""

from copy import deepcopy
from uuid import uuid4

import pytest
from test_answer_first_provider import setup
from test_council_chat import drain
from test_unified_council import create
from test_workflow import post

from zerowall.db import DomainError


def edit(client, view, message, text, **kwargs):
    return client.post(
        f"/api/chats/{view['chat']['id']}/messages/{message['id']}/regenerate",
        headers={"Idempotency-Key": kwargs.pop("key", str(uuid4()))},
        json={"text": text, "expected_revision": view["chat"]["revision"], **kwargs},
    )


@pytest.mark.parametrize("protocol", ["reviewed_v4", "reviewed_v3", "reviewed_v2"])
def test_edit_root_replaces_question_preserves_history_and_completes_full_review(
    client, app, protocol
):
    initial = create(
        client,
        review_protocol=protocol,
        prompt="WRONG_REQUEST evaluate cooling options.",
    )
    cid = initial["chat"]["id"]
    drain(app)
    before = client.get("/api/chats/" + cid).json()
    r = app.state.research
    with r.store.tx() as c:
        originals = deepcopy(r.chat.messages(c, before["chat"]))
        old_protocol = deepcopy(before["chat"]["protocol"])
    corrected = "CORRECTED_REQUEST evaluate memory transfer options."
    response = edit(client, before, originals[0], corrected, key="root-edit")
    assert response.is_success, response.text
    revised = response.json()
    assert revised["review"]["contract"]["question"] == corrected
    new_message = revised["messages"][-1]
    assert new_message["edited_from_message_id"] == originals[0]["id"]
    assert new_message["phase"] == "prompt" and not new_message["superseded"]
    assert all(m["superseded"] for m in revised["messages"][: len(originals)])
    # Identical idempotency key cannot queue or append twice.
    again = edit(client, before, originals[0], corrected, key="root-edit")
    assert again.json() == revised
    with r.store.tx() as c:
        chat = r.store.get(c, cid, "chat")
        assert r.chat.messages(c, chat)[: len(originals)] == originals
        turn = r.chat.next_turn(chat, r.chat.messages(c, chat), c)
        prompt, ids = r.chat.prompt(chat, r.chat.messages(c, chat), turn, c)
        assert corrected in prompt and "WRONG_REQUEST" not in prompt
        assert set(ids).isdisjoint({m["id"] for m in originals})
        assert chat["protocol"]["prompt"] == old_protocol["prompt"]
    drain(app)
    after = client.get("/api/chats/" + cid).json()
    assert after["chat"]["status"] == "completed", after["chat"].get("error")
    assert [
        m["phase"]
        for m in after["messages"]
        if m["role"] == "assistant" and not m["superseded"]
    ] == [
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


def test_edit_followup_keeps_preceding_context_only_and_later_edits_use_the_right_branch(
    client, app
):
    initial = create(
        client,
        review_protocol="reviewed_v4",
        prompt="ROOT compare memory transfer approaches.",
    )
    cid = initial["chat"]["id"]
    drain(app)
    first = client.get("/api/chats/" + cid).json()
    post(
        client,
        f"/chats/{cid}/messages",
        {"text": "WRONG_FOLLOWUP prioritize the largest price."},
    )
    drain(app)
    post(
        client,
        f"/chats/{cid}/messages",
        {"text": "LATER_WRONG_BRANCH use those expensive recommendations."},
    )
    drain(app)
    before = client.get("/api/chats/" + cid).json()
    wrong = next(
        m
        for m in before["messages"]
        if "WRONG_FOLLOWUP" in m["content"] and m["role"] == "user"
    )
    response = edit(client, before, wrong, "FIXED_FOLLOWUP minimize price instead.")
    assert response.is_success, response.text
    corrected = response.json()
    assert corrected["review"]["contract"]["question"].startswith("ROOT")
    r = app.state.research
    with r.store.tx() as c:
        chat = r.store.get(c, cid, "chat")
        prompt, ids = r.chat.prompt(
            chat,
            r.chat.messages(c, chat),
            r.chat.next_turn(chat, r.chat.messages(c, chat), c),
            c,
        )
        assert (
            "FIXED_FOLLOWUP" in prompt
            and "WRONG_FOLLOWUP" not in prompt
            and "LATER_WRONG_BRANCH" not in prompt
        )
        assert first["messages"][0]["id"] in ids
    drain(app)
    after = client.get("/api/chats/" + cid).json()
    post(
        client, f"/chats/{cid}/messages", {"text": "Now compare implementation effort."}
    )
    drain(app)
    after = client.get("/api/chats/" + cid).json()
    revised_root = edit(
        client, after, first["messages"][0], "NEW_ROOT compare power efficiency only."
    )
    assert revised_root.is_success, revised_root.text
    drain(app)
    after = client.get("/api/chats/" + cid).json()
    root = next(
        m for m in after["messages"] if m["role"] == "user" and not m["superseded"]
    )
    second_edit = edit(client, after, root, "SECOND_ROOT compare latency only.")
    assert second_edit.is_success, second_edit.text
    assert (
        second_edit.json()["review"]["contract"]["question"]
        == "SECOND_ROOT compare latency only."
    )
    drain(app)
    post(client, f"/chats/{cid}/messages", {"text": "Compare the costs too."})
    latest = client.get("/api/chats/" + cid).json()
    assert "SECOND_ROOT" in latest["review"]["contract"]["question"]
    assert "ROOT compare memory" not in latest["review"]["contract"]["question"]


@pytest.mark.parametrize("mode", ["normal", "first_unknown"])
def test_paid_edit_retains_money_and_dispatches_corrected_question_only(
    client, app, monkeypatch, mode
):
    r, cid, physical = setup(client, app, monkeypatch, mode)
    drain(app)
    before = client.get("/api/chats/" + cid).json()
    with r.store.tx() as c:
        old_calls = deepcopy(r.store.list(c, "call", before["chat"]["mission_id"]))
        money = {
            call["reservation_id"]: tuple(
                c.execute(
                    "SELECT * FROM reservations WHERE id=?", (call["reservation_id"],)
                ).fetchone()
            )
            for call in old_calls
        }
        old_messages = deepcopy(r.chat.messages(c, before["chat"]))
    if mode == "first_unknown":
        denied = edit(
            client, before, before["messages"][0], "CORRECTED paid mock request."
        )
        assert denied.status_code == 409 and "unknown charge" in denied.text
    count = len(physical)
    response = edit(
        client,
        before,
        before["messages"][0],
        "CORRECTED paid mock request.",
        authorize_retry_with_unknown_charge=True,
    )
    assert response.is_success, response.text
    assert (
        len(physical) == count
    )  # Merely enqueued, never dispatched inside the mutation.
    assert not response.json()["chat"].get("pending_request_recovery")
    drain(app)
    after = client.get("/api/chats/" + cid).json()
    assert after["chat"]["status"] == "completed", after["chat"].get("error")
    assert "CORRECTED paid mock request." in str(physical[count]["messages"])
    assert all(
        "Compare engineering pilots" not in str(p["messages"]) for p in physical[count:]
    )
    assert after["budget"]["unknown_usd"] == before["budget"]["unknown_usd"]
    with r.store.tx() as c:
        for call in old_calls:
            assert r.store.get(c, call["id"], "call") == call
            assert (
                tuple(
                    c.execute(
                        "SELECT * FROM reservations WHERE id=?",
                        (call["reservation_id"],),
                    ).fetchone()
                )
                == money[call["reservation_id"]]
            )
        assert r.chat.messages(c, after["chat"])[: len(old_messages)] == old_messages


def test_invalid_stale_or_busy_edits_never_change_history_or_queue_jobs(client, app):
    initial = create(client, review_protocol="reviewed_v4")
    cid = initial["chat"]["id"]
    busy = edit(client, initial, initial["messages"][0], "A changed question.")
    assert busy.status_code == 409
    drain(app)
    view = client.get("/api/chats/" + cid).json()
    other = create(client, review_protocol="reviewed_v4")
    drain(app)
    for message, values in [
        (view["messages"][1], {}),
        (other["messages"][0], {}),
        (view["messages"][0], {"expected_revision": 9999}),
    ]:
        response = edit(client, view, message, "A changed question.", **values)
        assert response.status_code in (409, 422)
    response = edit(client, view, view["messages"][0], " ")
    assert response.status_code == 422
    assert client.get("/api/chats/" + cid).json()["messages"] == view["messages"]
    assert not app.state.executor.run_once()


def test_rejected_new_execution_window_rolls_back_the_entire_edit(
    client, app, monkeypatch
):
    r, cid, physical = setup(client, app, monkeypatch, "normal")
    drain(app)
    before = client.get("/api/chats/" + cid).json()
    with r.store.tx() as c:
        records = [tuple(row) for row in c.execute("SELECT * FROM records ORDER BY id")]
        money = [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY id")
        ]
        jobs = [tuple(row) for row in c.execute("SELECT * FROM jobs ORDER BY id")]
    count = len(physical)

    def no_credit(*args, **kwargs):
        raise DomainError("Existing-credit allowance unavailable", 402)

    monkeypatch.setattr(r.chat.runtime, "begin_window", no_credit)
    response = edit(
        client, before, before["messages"][0], "An edit without sufficient credit."
    )
    assert response.status_code == 402
    assert len(physical) == count
    with r.store.tx() as c:
        assert [
            tuple(row) for row in c.execute("SELECT * FROM records ORDER BY id")
        ] == records
        assert [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY id")
        ] == money
        assert [
            tuple(row) for row in c.execute("SELECT * FROM jobs ORDER BY id")
        ] == jobs
