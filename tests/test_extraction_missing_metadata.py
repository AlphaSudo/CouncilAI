"""Sparse extraction metadata must not discard paid work or create evidence."""

import json
from copy import deepcopy

import pytest

from test_review_admission import completed_rejected_reply, extraction_context
from zerowall.db import DomainError
from zerowall.review_admission import MISSING_OBSERVATION_REASON, normalize_extraction
from zerowall.review_reply_restore import restore_completed_review


def sparse_extraction(output):
    output = deepcopy(output)
    output["observations"] = [
        {"source_message_id": claim["source_message_id"],
         "source_unit_id": claim["source_unit_ids"][0],
         "classification": "hypothetical", "trace_reference": "model-described fragment"}
        for claim in output["claims"][:2]
    ]
    output["observation_status"] = "complete_as_assessed"
    output["audits"] = [{
        "claim_ref": output["claims"][0]["ref"],
        "source_unit_ids": output["claims"][0]["source_unit_ids"],
        "kind": "resource", "scope": "Declared hypothetical resource boundary",
        "boundary": "Illustrative resource accounting, not an execution result",
        "is_ratio": True, "numerator": None, "denominator": None,
    }]
    return output


@pytest.mark.parametrize("reason", [None, "", "   ", "absent"])
def test_missing_explanation_is_disclosed_without_inventing_classification(reason):
    observation = {"classification": "hypothetical", "trace_reference": "not a rationale"}
    if reason != "absent":
        observation["reason"] = reason
    raw = {"observations": [observation], "observation_status": "complete_as_assessed"}
    original = deepcopy(raw)
    output, changes = normalize_extraction(raw)
    assert raw == original
    assert output["observations"][0]["reason"] == MISSING_OBSERVATION_REASON
    assert output["observations"][0]["classification"] == "hypothetical"
    assert output["observation_status"] == "partial"
    assert changes[0]["kind"] == "missing_observation_rationale"
    assert normalize_extraction(output) == (output, [])


def test_sparse_observations_and_null_ratio_terms_are_admitted_as_incomplete(client, app):
    research, cid = extraction_context(client, app)
    with research.store.tx() as c:
        chat = research.store.get(c, cid, "chat")
        messages = research.chat.messages(c, chat)
        turn = research.chat.next_turn(chat, messages, c)
        output = sparse_extraction(json.loads(research.chat.review.demo(c, chat, messages, turn)))
        public = research.chat.review.admit(c, chat, turn, json.dumps(output), "sparse-metadata")
        snap = research.chat.review.snapshot(c, chat)
        assert len(snap["claims"]) == len(output["claims"])
        assert len(snap["observations"]) == 2
        assert all(o["status"] == "unverified_report" for o in snap["observations"])
        assert all(o["reason"] == MISSING_OBSERVATION_REASON for o in snap["observations"])
        assert snap["observation_status"] == "partial"
        audit = snap["audit_descriptors"][0]
        assert audit["numerator"] == audit["denominator"] == ""
        assert snap["audit_results"][0]["state"] == "incomplete"
        assert "ratio numerator or denominator is missing" in snap["audit_results"][0]["reason"]
        assert "rationales were not supplied" in public
        assert len(snap["admission_records"][0]["changes"]) == 5
        assert not snap["evidence"]


@pytest.mark.parametrize("violation", ["source", "coverage", "classification", "ratio_object"])
def test_metadata_normalization_keeps_authoritative_validation_atomic(client, app, violation):
    research, cid = extraction_context(client, app)
    with research.store.tx() as c:
        chat = research.store.get(c, cid, "chat")
        messages = research.chat.messages(c, chat)
        turn = research.chat.next_turn(chat, messages, c)
        output = sparse_extraction(json.loads(research.chat.review.demo(c, chat, messages, turn)))
        if violation == "source":
            output["observations"][0]["source_unit_id"] = "nonexistent-unit"
        elif violation == "coverage":
            output["coverage"].pop()
        elif violation == "classification":
            output["observations"][0]["classification"] = "verified_experiment"
        else:
            output["audits"][0]["numerator"] = {"value": 1}
        with pytest.raises(DomainError):
            research.chat.review.admit(c, chat, turn, json.dumps(output), "rejected-metadata")
        snap = research.chat.review.snapshot(c, chat)
        assert not snap["claims"] and not snap["observations"]
        assert not snap["admission_records"]


def test_structured_observation_reason_is_only_unverified_model_prose(client, app):
    research, cid = extraction_context(client, app)
    with research.store.tx() as c:
        chat = research.store.get(c, cid, "chat")
        messages = research.chat.messages(c, chat)
        turn = research.chat.next_turn(chat, messages, c)
        output = sparse_extraction(json.loads(research.chat.review.demo(c, chat, messages, turn)))
        output["observations"][0]["reason"] = {"verified": True}
        research.chat.review.admit(c, chat, turn, json.dumps(output), "structured-reason-note")
        snap = research.chat.review.snapshot(c, chat)
        assert snap["observations"][0]["reason"] == "verified: true"
        assert snap["observations"][0]["status"] == "unverified_report"
        assert not snap["evidence"]
        change = next(change for change in snap["admission_records"][0]["changes"]
                      if change.get("path") == ["observations", 0, "reason"])
        assert change["before"] == {"verified": True} and change["kind"] == "structured_prose"


def test_saved_sparse_extraction_is_restored_once_with_no_new_calls_or_charges(client, app, monkeypatch):
    research, chat, call, physical = completed_rejected_reply(
        client, app, monkeypatch, extraction_transform=sparse_extraction)
    with research.store.tx() as c:
        calls = research.store.list(c, "call", chat["mission_id"])
        reservations = [tuple(r) for r in c.execute("SELECT * FROM reservations ORDER BY rowid")]
    result = restore_completed_review(research, call["id"])
    assert result["new_inference_calls"] == 0 and result["financial_records_changed"] is False
    assert result["status"] == "paused"
    view = client.get("/api/chats/" + chat["id"]).json()
    assert view["next_turn"]["phase"] == "scrutiny"
    assert view["chat"]["error"] is None
    assert view["review"]["observation_status"] == "partial"
    assert len(physical) == 4 and not app.state.executor.run_once()
    with research.store.tx() as c:
        assert research.store.list(c, "call", chat["mission_id"]) == calls
        assert [tuple(r) for r in c.execute("SELECT * FROM reservations ORDER BY rowid")] == reservations
    assert restore_completed_review(research, call["id"]) == result
