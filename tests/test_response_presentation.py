"""Public replies survive formatting/reference faults without another request."""

import json

import pytest
from test_council_chat import drain
from test_unified_council import create

from zerowall.council_review_v3 import UnifiedCouncil
from zerowall.council_review_v4 import AnswerFirstCouncil
from zerowall.response_presentation import readable_reply


def test_structured_reply_retains_every_supplied_public_field():
    raw = json.dumps(
        {
            "findings": [
                {
                    "objection": "The gain uses a different baseline.",
                    "minimum_resolution": "Use a matched baseline.",
                    "candidate_test": "Measure sustained bandwidth.",
                    "checks": [
                        {
                            "category": "provenance",
                            "reason": "Inputs unverified.",
                            "status": "unknown",
                        }
                    ],
                    "novel_extra": {"details": ["Keep this original idea."]},
                }
            ],
            "notes": [{"reason": "The other attack did not defeat the claim."}],
            "limitations": "No experiments were run.",
        }
    )
    rendered = readable_reply(raw, "scrutiny")
    for text in (
        "different baseline",
        "matched baseline",
        "sustained bandwidth",
        "Inputs unverified",
        "Keep this original idea",
        "did not defeat",
        "No experiments",
    ):
        assert text in rendered
    assert "model's judgments" in rendered


@pytest.mark.parametrize(
    "raw",
    [
        '## Answer\n\nExample: {"value": 1}\n\nKeep this conclusion.',
        '```json\n{"value": 1}\n```\n\nThis caveat must remain.',
        '{"value": 1, "value": 2}',
        '{"findings": [unfinished',
        '[{"text": "First"}, {"text": "Second"}] trailing caveat',
    ],
)
def test_ambiguous_or_mixed_public_text_remains_intact(raw):
    assert readable_reply(raw, "scrutiny") == raw


def test_original_endpoint_preserves_exact_text_and_history_without_inference(
    client, app
):
    initial = create(client, review_protocol="reviewed_v4")
    cid = initial["chat"]["id"]
    drain(app)
    before = client.get("/api/chats/" + cid).json()
    message = next(m for m in before["messages"] if m["phase"] == "extraction")
    assert message["original_response_available"]
    store = app.state.research.store
    with store.tx() as c:
        row = c.execute(
            "SELECT body FROM records WHERE kind='answer_delivery' AND json_extract(body,'$.message_id')=?",
            (message["id"],),
        ).fetchone()
        original = json.loads(row[0])["raw_public_content"]
        calls = store.list(c, "call", initial["chat"]["mission_id"])
        reservations = [
            tuple(r) for r in c.execute("select * from reservations order by id")
        ]
    response = client.get(f"/api/chats/{cid}/messages/{message['id']}/original")
    assert response.is_success, response.text
    assert response.json()["content"] == original
    assert response.json()["readable"] == readable_reply(original, "extraction")
    assert response.json()["new_inference_calls"] == 0
    assert client.get("/api/chats/" + cid).json()["messages"] == before["messages"]
    other = create(client, review_protocol="reviewed_v4")
    assert (
        client.get(
            f"/api/chats/{other['chat']['id']}/messages/{message['id']}/original"
        ).status_code
        == 404
    )
    with store.tx() as c:
        assert store.list(c, "call", initial["chat"]["mission_id"]) == calls
        assert [
            tuple(r) for r in c.execute("select * from reservations order by id")
        ] == reservations


def test_source_ids_in_evidence_slot_keep_objection_without_granting_evidence(
    client, app, monkeypatch
):
    original = UnifiedCouncil.demo

    def wrong_reference(self, c, chat, messages, turn):
        raw = original(self, c, chat, messages, turn)
        if turn["phase"] == "scrutiny":
            value = json.loads(raw)
            assert value["findings"]
            value["findings"][0]["evidence_ids"] = [
                "version_a_document_not_a_review_evidence_record"
            ]
            return json.dumps(value)
        return raw

    monkeypatch.setattr(UnifiedCouncil, "demo", wrong_reference)
    initial = create(client, review_protocol="reviewed_v4")
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    finding = next(
        f for f in view["review"]["findings"] if f.get("unlinked_evidence_references")
    )
    assert finding["evidence_ids"] == []
    assert finding["reference_status"] == "unverified"
    assert finding["objection"]
    assert any(m["phase"] == "repair" for m in view["messages"])
    assert view["messages"][-1]["phase"] == "synthesis"


def test_annotation_summary_cannot_overwrite_a_committed_reply(
    client, app, monkeypatch
):
    original = AnswerFirstCouncil._admit

    def shorter_summary(self, c, chat, turn, content, message_id):
        rendered = original(self, c, chat, turn, content, message_id)
        return (
            "A deliberately shortened ledger summary."
            if turn["phase"] == "extraction"
            else rendered
        )

    monkeypatch.setattr(AnswerFirstCouncil, "_admit", shorter_summary)
    initial = create(client, review_protocol="reviewed_v4")
    drain(app)
    cid = initial["chat"]["id"]
    view = client.get("/api/chats/" + cid).json()
    assert view["chat"]["status"] == "completed"
    message = next(m for m in view["messages"] if m["phase"] == "extraction")
    saved = client.get(f"/api/chats/{cid}/messages/{message['id']}/original").json()
    assert message["content"] == saved["readable"]
    assert "deliberately shortened" not in message["content"]
