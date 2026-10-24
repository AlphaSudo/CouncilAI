"""Answer-first durability and finite progression; fixtures never assert answer quality."""

import json
import sqlite3
from contextlib import closing

import pytest
from test_council_chat import drain
from test_unified_council import create

from zerowall.council_review_v3 import UnifiedCouncil
from zerowall.council_review_v4 import AnswerFirstCouncil


def test_public_answer_committed_before_review_starts(client, app, monkeypatch):
    seen = []
    original = AnswerFirstCouncil._admit

    def inspect(self, c, chat, turn, content, message_id):
        # A separate connection must see it: a savepoint in this transaction is insufficient.
        with closing(sqlite3.connect(self.store.path)) as other:
            saved = json.loads(
                other.execute(
                    "SELECT body FROM records WHERE id=?", (message_id,)
                ).fetchone()[0]
            )
            assert saved["generation_state"] == "complete"
            assert saved["review_state"] == "pending"
            assert saved["raw_public_hash"]
            seen.append(turn["phase"])
        return original(self, c, chat, turn, content, message_id)

    monkeypatch.setattr(AnswerFirstCouncil, "_admit", inspect)
    initial = create(client, review_protocol="reviewed_v4")
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed"
    assert seen
    assert all(
        s["state"] in ("success", "partial", "degraded", "skipped")
        for s in view["stage_results"]
    )
    assert view["messages"][-1]["generation_state"] == "complete"


@pytest.mark.parametrize("phase", ["extraction", "scrutiny", "repair", "recheck"])
def test_entire_sidecar_bug_keeps_public_delivery(client, app, monkeypatch, phase):
    original = AnswerFirstCouncil._admit

    def broken(self, c, chat, turn, content, message_id):
        if turn["phase"] == phase:
            raise RuntimeError("Synthetic sidecar failure")
        return original(self, c, chat, turn, content, message_id)

    monkeypatch.setattr(AnswerFirstCouncil, "_admit", broken)
    initial = create(client, review_protocol="reviewed_v4")
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert view["chat"]["generation_state"] == "complete"
    assert view["chat"]["review_state"] == "incomplete"
    assert any(
        s["state"] == "degraded" and s["phase"] == phase for s in view["stage_results"]
    )
    assert view["messages"][-1]["phase"] == "synthesis"
    assert not app.state.executor.run_once()


def test_final_is_markdown_without_publication_envelope(client, app, monkeypatch):
    original = UnifiedCouncil.demo
    final = "Prefer the reversible pilot.\n\nUnconventional alternatives remain possible; measure their cost before ranking them."

    def demo(self, c, chat, messages, turn):
        return (
            final
            if turn["phase"] == "synthesis"
            else original(self, c, chat, messages, turn)
        )

    monkeypatch.setattr(UnifiedCouncil, "demo", demo)
    initial = create(client, review_protocol="reviewed_v4")
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed"
    assert view["messages"][-1]["content"] == final
    assert view["review"]["contract"]["policy_version"] == "generic-publication-v4"


def test_three_followups_preserve_frozen_prior_answers(client, app):
    initial = create(client, review_protocol="reviewed_v4")
    cid = initial["chat"]["id"]
    drain(app)
    before = client.get("/api/chats/" + cid).json()["messages"]
    for i in range(3):
        response = client.post(
            "/api/chats/" + cid + "/messages",
            headers={"Idempotency-Key": f"answer-first-followup-{i}"},
            json={"text": f"Reconsider implementation under constraint {i}."},
        )
        assert response.is_success, response.text
        drain(app)
        after = client.get("/api/chats/" + cid).json()
        assert after["chat"]["status"] == "completed", after["chat"].get("error")
        assert after["messages"][: len(before)] == before
        before = after["messages"]
    assert after["review"]["cycle"] == 4
