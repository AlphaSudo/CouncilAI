"""Formatting recovery never creates evidence or bypasses source validation."""

import json
from copy import deepcopy

import httpx
import pytest
from test_council_chat import drain
from test_token_factory_generation import sse
from test_token_factory_research import setup_testing
from test_unified_council import create

from zerowall.council_review_v3 import UnifiedCouncil
from zerowall.db import DomainError, digest
from zerowall.review_reply_restore import restore_completed_review


def imperfect_extraction(output):
    output = deepcopy(output)
    output["claims"][0]["reasoning_kind"] = "calculation"
    output["claims"][1]["reasoning_kind"] = "quantitative"
    output["audits"] = [
        {
            "claim_ref": output["claims"][0]["ref"],
            "source_unit_ids": output["claims"][0]["source_unit_ids"],
            "kind": "calculation",
            "scope": "A declared hypothetical arithmetic expression",
            "expression": "1+1",
            "expected_value": "2",
            "absolute_tolerance": None,
        }
    ]
    base = output["families"][0]
    output["families"] = [
        {
            **base,
            "name": f"Candidate approach {index}",
            "mechanism": f"Illustrative mechanism {index} with its own declared boundary",
            "refs": [claim["ref"]],
        }
        for index, claim in enumerate(output["claims"])
    ]
    output["groups"] = [
        {
            "refs": [output["claims"][0]["ref"], output["claims"][1]["ref"]],
            "relation": "equivalent_as_assessed",
            "reason": "These two assertions were assessed as equivalent",
        }
    ]
    return output


def extraction_context(client, app):
    initial = create(client)
    for _ in range(3):
        assert app.state.executor.run_once()
    research = app.state.research
    return research, initial["chat"]["id"]


def test_local_normalization_preserves_uncertainty_and_disputed_families(client, app):
    research, cid = extraction_context(client, app)
    with research.store.tx() as c:
        chat = research.store.get(c, cid, "chat")
        messages = research.chat.messages(c, chat)
        turn = research.chat.next_turn(chat, messages, c)
        value = imperfect_extraction(
            json.loads(research.chat.review.demo(c, chat, messages, turn))
        )
        raw = json.dumps(value)
        public = research.chat.review.admit(c, chat, turn, raw, "saved-normalization")
        snapshot = research.chat.review.snapshot(c, chat)
        assert [claim["reasoning_kind"] for claim in snapshot["claims"][:2]] == [
            "unclear",
            "unclear",
        ]
        assert snapshot["audit_descriptors"][0]["absolute_tolerance"] == "unknown"
        assert snapshot["audit_results"][0]["state"] == "unknown"
        assert len(snapshot["families"]) == 3
        assert [family["distinct_as_assessed"] for family in snapshot["families"]] == [
            False,
            False,
            True,
        ]
        assert all(
            claim["fidelity"] == value["claims"][index]["fidelity"]
            for index, claim in enumerate(snapshot["claims"])
        )
        adjustments = snapshot["admission_records"][0]
        assert adjustments["raw_content_hash"] == digest(raw)
        assert [change["before"] for change in adjustments["changes"]] == [
            "calculation",
            "quantitative",
            None,
        ]
        assert (
            "disputed candidates" in public
            and "null audit tolerance remains unknown" in public
        )
        assert [claim["reasoning_kind"] for claim in value["claims"][:2]] == [
            "calculation",
            "quantitative",
        ]


@pytest.mark.parametrize(
    "violation,expected",
    [
        ("source", "unknown source"),
        ("coverage", "Coverage must include all opening messages"),
        ("schema", "audits.0.absolute_tolerance"),
    ],
)
def test_unrepairable_inputs_still_fail_atomically_with_specific_error(
    client, app, violation, expected
):
    research, cid = extraction_context(client, app)
    with research.store.tx() as c:
        chat = research.store.get(c, cid, "chat")
        messages = research.chat.messages(c, chat)
        turn = research.chat.next_turn(chat, messages, c)
        value = imperfect_extraction(
            json.loads(research.chat.review.demo(c, chat, messages, turn))
        )
        if violation == "source":
            value["claims"][0]["source_unit_ids"] = ["nonexistent-source-unit"]
        elif violation == "coverage":
            value["coverage"].pop()
        else:
            value["audits"][0]["absolute_tolerance"] = {
                "private": "INPUT_MUST_NOT_APPEAR_IN_ERROR"
            }
        with pytest.raises(DomainError, match=expected) as failure:
            research.chat.review.admit(
                c, chat, turn, json.dumps(value), "rejected-local-repair"
            )
        assert "INPUT_MUST_NOT_APPEAR_IN_ERROR" not in failure.value.message
        assert not research.chat.review.snapshot(c, chat)["claims"]
        assert not research.store.list(c, "review_admission", chat["mission_id"])


def completed_rejected_reply(client, app, monkeypatch, phase="extraction", extraction_transform=imperfect_extraction):
    from zerowall.review_delivery import admit_deliverable as current_delivery
    research = setup_testing(app)
    original, physical = httpx.Client, []
    attempts = {
        "extraction": 4,
        "scrutiny": 5,
        "repair": 6,
        "recheck": 9,
        "synthesis": 10,
    }[phase]

    def handler(request):
        body = json.loads(request.content)
        physical.append(body)
        assert len(physical) <= attempts, "Local recovery dispatched a new request"
        with research.store.tx() as c:
            chat = json.loads(
                c.execute(
                    "SELECT body FROM records WHERE kind='chat' ORDER BY rowid DESC LIMIT 1"
                ).fetchone()[0]
            )
            messages = research.chat.messages(c, chat)
            turn = research.chat.next_turn(chat, messages, c)
            if turn["phase"] == "opening":
                demo_turn = deepcopy(turn)
                demo_turn["participant"]["model"] = [
                    "demo/analyst",
                    "demo/critic",
                    "demo/builder",
                ][len(physical) - 1]
                text = research.chat.demo_answer(chat, messages, demo_turn)
            elif turn["phase"] == "extraction":
                text = json.dumps(
                    extraction_transform(
                        json.loads(research.chat.review.demo(c, chat, messages, turn))
                    )
                )
            elif turn["phase"] == "scrutiny":
                output = json.loads(research.chat.review.demo(c, chat, messages, turn))
                output["findings"][0]["evidence_obligation"] = (
                    "Independent evidence is still needed; this is model commentary."
                )
                text = json.dumps(output)
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
    actual_admit = research.chat.review.admit

    def former_validator(c, chat, turn, content, message_id):
        if turn["phase"] == phase:
            raise DomainError("Former extraction schema rejection", 422)
        return actual_admit(c, chat, turn, content, message_id)

    monkeypatch.setattr(research.chat.review, "admit", former_validator)
    # Reconstruct a historical pre-fix failure. The production delivery path now
    # continues through this 422, so use the old strict boundary for fixture setup.
    monkeypatch.setattr("zerowall.review_delivery.admit_deliverable",
                        lambda council, c, chat, turn, content, message_id:
                        council.review.admit(c, chat, turn, content, message_id))
    response = client.post(
        "/api/chats",
        headers={"Idempotency-Key": "saved-review-recovery"},
        json={
            "review_protocol": "reviewed_v3",
            "provider": "nebius_token_factory",
            "prompt": "Compare bounded engineering alternatives.",
            "models": research.settings.policy["council_default_models"],
            "budget_usd": 1,
        },
    )
    assert response.is_success, response.text
    for _ in range(attempts):
        assert app.state.executor.run_once()
    monkeypatch.setattr(research.chat.review, "admit", actual_admit)
    monkeypatch.setattr("zerowall.review_delivery.admit_deliverable", current_delivery)
    with research.store.tx() as c:
        chat = research.store.get(c, response.json()["chat"]["id"], "chat")
        assert chat["status"] == "failed"
        call = research.store.list(c, "call", chat["mission_id"])[-1]
    return research, chat, call, physical


def test_saved_scrutiny_preserves_extra_evidence_note_without_new_calls(
    client, app, monkeypatch
):
    research, chat, call, physical = completed_rejected_reply(
        client, app, monkeypatch, phase="scrutiny"
    )
    with research.store.tx() as c:
        calls_before = research.store.list(c, "call", chat["mission_id"])
        financial_before = [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY rowid")
        ]
        claims_before = research.chat.review.snapshot(c, chat)["claims"]
    result = restore_completed_review(research, call["id"])
    view = client.get("/api/chats/" + chat["id"]).json()
    assert view["chat"]["status"] == "paused" and view["next_turn"]["phase"] == "repair"
    assert len(view["review"]["findings"]) == len(claims_before)
    assert (
        view["review"]["findings"][0]["evidence_obligation"]
        == "Independent evidence is still needed; this is model commentary."
    )
    assert "Evidence notes (model commentary)" in view["messages"][-1]["content"]
    assert view["review"]["claims"] == claims_before
    assert result["new_inference_calls"] == 0 and len(physical) == 5
    assert not app.state.executor.run_once()
    with research.store.tx() as c:
        assert research.store.list(c, "call", chat["mission_id"]) == calls_before
        assert [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY rowid")
        ] == financial_before
    assert restore_completed_review(research, call["id"]) == result


@pytest.mark.parametrize(
    "violation",
    ["unknown_extra", "unrelated_evidence", "stale_revision", "missing_claim"],
)
def test_optional_finding_commentary_does_not_weaken_scrutiny_checks(
    client, app, violation
):
    research, cid = extraction_context(client, app)
    assert app.state.executor.run_once()
    with research.store.tx() as c:
        chat = research.store.get(c, cid, "chat")
        messages = research.chat.messages(c, chat)
        turn = research.chat.next_turn(chat, messages, c)
        output = json.loads(research.chat.review.demo(c, chat, messages, turn))
        output["findings"][0]["evidence_obligation"] = (
            "This is an unverified model note."
        )
        if violation == "unknown_extra":
            output["findings"][0]["human_verified"] = True
        elif violation == "unrelated_evidence":
            output["findings"][0]["evidence_ids"] = ["nonexistent-evidence"]
        elif violation == "stale_revision":
            output["findings"][0]["claim_revision"] = 999
        else:
            output["findings"].pop()
        with pytest.raises(DomainError):
            research.chat.review.admit(
                c, chat, turn, json.dumps(output), "invalid-scrutiny"
            )
        assert not research.chat.review.snapshot(c, chat)["findings"]


def test_saved_completed_reply_is_recovered_once_without_inference_or_finance_changes(
    client, app, monkeypatch
):
    research, chat, call, physical = completed_rejected_reply(client, app, monkeypatch)
    with research.store.tx() as c:
        previous_calls = research.store.list(c, "call", chat["mission_id"])
        reservations = [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY rowid")
        ]
    result = restore_completed_review(research, call["id"])
    view = client.get("/api/chats/" + chat["id"]).json()
    assert view["chat"]["status"] == "paused" and view["chat"]["error"] is None
    assert view["next_turn"]["phase"] == "scrutiny"
    assert view["messages"][-1]["call_id"] == call["id"]
    assert view["messages"][-1]["context_hash"] == call["request_hash"]
    assert view["messages"][-1]["context_hash_kind"] == "saved_provider_request"
    assert (
        result["new_inference_calls"] == 0
        and result["financial_records_changed"] is False
    )
    assert len(physical) == 4 and not app.state.executor.run_once()
    with research.store.tx() as c:
        assert research.store.list(c, "call", chat["mission_id"]) == previous_calls
        assert [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY rowid")
        ] == reservations
    assert restore_completed_review(research, call["id"]) == result
    assert len(client.get("/api/chats/" + chat["id"]).json()["messages"]) == len(
        view["messages"]
    )


def test_changed_sources_prevent_reusing_a_stale_saved_review_reply(
    client, app, monkeypatch
):
    research, chat, call, physical = completed_rejected_reply(client, app, monkeypatch)
    research.library.ingest(
        chat, b"A new constraint changes the task.", title="Changed input"
    )
    with pytest.raises(DomainError, match="unchanged council turn"):
        restore_completed_review(research, call["id"])
    assert len(physical) == 4
    with research.store.tx() as c:
        assert not research.store.list(
            c, "review_reply_restoration", chat["mission_id"]
        )
        assert not research.chat.review.snapshot(c, chat)["claims"]


@pytest.mark.parametrize("exclude_duplicate", [False, True])
def test_duplicate_families_need_a_consistent_current_recheck(
    client, app, monkeypatch, exclude_duplicate
):
    original = UnifiedCouncil.demo

    def demo(self, c, chat, messages, turn):
        raw = original(self, c, chat, messages, turn)
        if turn["phase"] == "extraction":
            output = imperfect_extraction(json.loads(raw))
            output["families"][1]["refs"] = output["families"][0]["refs"]
            return json.dumps(output)
        if turn["phase"] == "recheck" and exclude_duplicate:
            output = json.loads(raw)
            output["families"][1]["still_distinct_as_assessed"] = False
            return json.dumps(output)
        return raw

    monkeypatch.setattr(UnifiedCouncil, "demo", demo)
    initial = create(client)
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert [family["distinct_as_assessed"] for family in view["review"]["families"]][
        :2
    ] == [exclude_duplicate, False]
    assert [
        family["assessment_history"][-1]["model_distinct_as_assessed"]
        for family in view["review"]["families"][:2]
    ] == [True, not exclude_duplicate]
