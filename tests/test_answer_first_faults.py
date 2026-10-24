"""Fault injection and local recovery evidence for answer-first; no paid API calls."""

import json

import pytest
from test_council_chat import drain
from test_unified_council import create

from zerowall.answer_delivery import AnswerDelivery, save_stream
from zerowall.artifacts import Artifacts
from zerowall.council_review_v3 import UnifiedCouncil


@pytest.mark.parametrize(
    "kind",
    [
        "invalid_source",
        "stale_audit",
        "authority",
        "missing_reason",
        "null_ratio",
        "family_prose",
        "long_prose",
        "repeated_json",
        "ambiguous_json",
    ],
)
def test_mixed_annotations_keep_independent_valid_records(
    client, app, monkeypatch, kind
):
    original = UnifiedCouncil.demo

    def demo(self, c, chat, messages, turn):
        raw = original(self, c, chat, messages, turn)
        if turn["phase"] != "extraction":
            return raw
        value = json.loads(raw)
        if kind == "invalid_source":
            value["claims"][0]["source_message_id"] = "unknown-source"
        if kind == "stale_audit":
            value["audits"] = [
                {
                    "claim_ref": "C99",
                    "kind": "reference",
                    "source_unit_ids": ["missing"],
                    "reference": "Unverified",
                }
            ]
        if kind == "authority":
            value["claims"][0]["human_verified"] = True
        if kind == "missing_reason":
            value["observations"] = [
                {
                    "source_message_id": value["claims"][0]["source_message_id"],
                    "source_unit_id": value["claims"][0]["source_unit_ids"][0],
                    "classification": "hypothetical",
                }
            ]
        if kind == "null_ratio":
            value["inventory_limitations"] = None
        if kind == "family_prose":
            value["families"][0]["assumptions"] = [
                "Known assumptions",
                {"condition": "No measurements"},
            ]
            value["families"][0]["resources"] = {"time": "Unknown", "cost": 0}
        if kind == "long_prose":
            value["claims"][0]["assertion"] += " This is an unmeasured proposal." * 60
        raw = json.dumps(value)
        if kind == "repeated_json":
            raw = raw + "\n" + raw
        if kind == "ambiguous_json":
            raw = raw + "\n" + json.dumps({"claims": []})
        return raw

    monkeypatch.setattr(UnifiedCouncil, "demo", demo)
    initial = create(client, review_protocol="reviewed_v4")
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert len([m for m in view["messages"] if m["phase"] == "opening"]) == 3
    assert view["messages"][-1]["content"]
    assert not view["review"]["evidence"]
    if kind in ("invalid_source", "authority"):
        assert len(view["review"]["claims"]) == 2
        assert view["review"]["quarantine"]
        assert all(q["grants_authority"] is False for q in view["review"]["quarantine"])
    if kind == "ambiguous_json":
        assert not view["review"]["claims"]
    assert not app.state.executor.run_once()


def test_crash_after_public_commit_recovers_once_without_billed_replay(
    client, app, monkeypatch
):
    r = app.state.research
    initial = create(client, review_protocol="reviewed_v4")
    cid = initial["chat"]["id"]
    original = AnswerDelivery.annotate

    def crash(*args, **kwargs):
        raise SystemExit("Synthetic crash after public commit")

    monkeypatch.setattr(AnswerDelivery, "annotate", crash)
    with pytest.raises(SystemExit):
        app.state.executor.run_once()
    before = client.get("/api/chats/" + cid).json()
    assert (
        len(before["messages"]) == 2
        and before["messages"][-1]["review_state"] == "pending"
    )
    with r.store.tx() as c:
        money = [tuple(row) for row in c.execute("SELECT * FROM reservations")]
    monkeypatch.setattr(AnswerDelivery, "annotate", original)
    r.store.recover()
    delivery = AnswerDelivery(r.chat)
    assert delivery.reconcile() == 1
    assert delivery.reconcile() == 0
    with r.store.tx() as c:
        assert [tuple(row) for row in c.execute("SELECT * FROM reservations")] == money
    drain(app)
    after = client.get("/api/chats/" + cid).json()
    assert after["chat"]["status"] == "completed"
    assert after["messages"][1]["id"] == before["messages"][1]["id"]
    assert after["messages"][1]["content"] == before["messages"][1]["content"]


def test_stream_redaction_crosses_flush_boundaries_without_reasoning_storage(
    client, app, tmp_path
):
    r = app.state.research
    initial = create(client, review_protocol="reviewed_v4")
    artifacts = Artifacts(tmp_path, ["secret-key-12345"])
    call = {
        "id": "stream-test",
        "mission_id": initial["chat"]["mission_id"],
        "model": "demo/analyst",
        "purpose": "chat:" + initial["chat"]["id"] + ":opening",
    }
    with r.store.tx() as c:
        save_stream(r.store, artifacts, c, call, ["Public before secret-ke"])
        first = r.store.get(c, "public_stream_stream-test", "public_stream")
        assert "".join(chunk["text"] for chunk in first["chunks"]) == "Public before "
        save_stream(
            r.store,
            artifacts,
            c,
            call,
            ["Public before secret-ke", "y-12345 after."],
            complete=True,
        )
        second = r.store.get(c, "public_stream_stream-test", "public_stream")
        assert (
            "".join(chunk["text"] for chunk in second["chunks"])
            == "Public before [REDACTED] after."
        )
        assert [chunk["seq"] for chunk in second["chunks"]] == [1, 2]
        save_stream(
            r.store,
            artifacts,
            c,
            call,
            ["Public before secret-key-12345 after."],
            complete=True,
        )
        assert r.store.get(c, second["id"], "public_stream") == second


def test_steering_is_queued_until_all_independent_answers_are_frozen(client, app):
    initial = create(client, review_protocol="reviewed_v4")
    cid = initial["chat"]["id"]
    app.state.executor.run_once()
    response = client.post(
        "/api/chats/" + cid + "/messages",
        headers={"Idempotency-Key": "queued-while-opening"},
        json={"text": "Consider portability in the final comparison."},
    )
    assert response.is_success and response.json()["queued_steering"]
    app.state.executor.run_once()
    mid = client.get("/api/chats/" + cid).json()
    assert not any(m.get("phase") == "intervention" for m in mid["messages"])
    app.state.executor.run_once()
    mid = client.get("/api/chats/" + cid).json()
    assert not mid["queued_steering"] and mid["messages"][-1]["role"] == "user"
    drain(app)
    assert client.get("/api/chats/" + cid).json()["chat"]["status"] == "completed"


def test_failed_attack_is_a_valid_note_and_does_not_force_repairs(
    client, app, monkeypatch
):
    original = UnifiedCouncil.demo

    def demo(self, c, chat, messages, turn):
        if turn["phase"] == "scrutiny":
            claims = self.snapshot(c, chat)["claims"]
            return json.dumps(
                {
                    "findings": [],
                    "notes": [
                        {
                            "claim_id": cl["claim_id"],
                            "claim_revision": cl["revision"],
                            "outcome": "attack_did_not_defeat_claim",
                            "reason": "No contradiction found under the stated assumptions.",
                        }
                        for cl in claims
                    ],
                    "limitations": "Not proof or external evidence.",
                }
            )
        return original(self, c, chat, messages, turn)

    monkeypatch.setattr(UnifiedCouncil, "demo", demo)
    initial = create(client, review_protocol="reviewed_v4")
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed"
    assert not view["review"]["findings"] and not view["review"]["evidence"]
    assert not any(m["phase"] == "repair" for m in view["messages"])
    assert len([s for s in view["stage_results"] if s["state"] == "skipped"]) == 4
