"""Whole-workflow compatibility tests, with adversarial authority boundaries."""

import io
import json
from copy import deepcopy

import httpx
import pytest
from test_council_chat import drain
from test_review_admission import completed_rejected_reply
from test_token_factory_generation import sse
from test_token_factory_research import setup_testing
from test_unified_council import create

from zerowall.council_review_v3 import UnifiedCouncil
from zerowall.db import DomainError, digest
from zerowall.review_admission import MAX_REVIEW_REPLY_BYTES
from zerowall.review_exports import verify_review_pack
from zerowall.review_reply_restore import restore_completed_review

PROSE = (
    "This proposal remains conditional on the declared boundary and its explicit assumptions. "
    * 36
)


def expand_prose(output, phase):
    output = deepcopy(output)
    output["notes"] = (
        "Supplementary public commentary; this does not establish verification."
    )
    if phase == "extraction":
        for claim in output["claims"]:
            for key in ("assertion", "scope", "materiality", "evidence_obligation"):
                claim[key] += " " + PROSE
        for item in output["coverage"]:
            item["omitted_material"] += PROSE
        for item in output["inventory"]:
            item["description"] += PROSE
        for family in output["families"]:
            for key in ("mechanism", "assumptions", "resources", "distinguishing_test"):
                family[key] += PROSE
        output["observation_coverage"] += PROSE
        output["inventory_limitations"] += PROSE
    elif phase == "scrutiny":
        output["limitations"] += PROSE
        for finding in output["findings"]:
            for key in (
                "steelman",
                "objection",
                "candidate_test",
                "minimum_resolution",
                "target",
                "in_scope_reason",
            ):
                finding[key] += PROSE
            for check in finding["checks"]:
                check["reason"] += PROSE
            for key in finding["test"]:
                finding["test"][key] += PROSE
    elif phase == "repair":
        output["explanation"] += PROSE
        for repair in output["repairs"]:
            for key in ("response", "revised_scope", "remaining_uncertainty"):
                repair[key] += PROSE
            repair["action"] = repair["action"].upper()  # Exact enum spelling only.
            if repair["revised_text"]:
                repair["revised_text"] += PROSE
    elif phase == "recheck":
        output["limitations"] += PROSE
        for assessment in output["assessments"]:
            assessment["comparison"] += PROSE
            assessment["test_reason"] += PROSE
            for concern in assessment["concerns"]:
                concern["detail"] += PROSE
                concern["affected_scope"] += PROSE
        for family in output["families"]:
            family["reason"] += PROSE
    elif phase == "synthesis":
        for block in output["blocks"]:
            block["text"] += "\n\n" + PROSE
        output["deliverable_limitations"] += PROSE
    return output


def test_long_valid_prose_and_extra_commentary_complete_the_full_council(
    client, app, monkeypatch
):
    research = setup_testing(app)
    original, physical = httpx.Client, []

    def handler(request):
        body = json.loads(request.content)
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
                ][len(physical)]
                text = research.chat.demo_answer(chat, messages, demo_turn)
            else:
                output = json.loads(research.chat.review.demo(c, chat, messages, turn))
                output = expand_prose(output, turn["phase"])
                if (
                    turn["phase"] == "repair"
                    and not turn.get("focused")
                    and turn["author_id"] == "member_3"
                ):
                    peer = next(
                        claim
                        for claim in research.chat.review.snapshot(c, chat)["claims"]
                        if claim["author_id"] != turn["author_id"]
                    )
                    output["peer_challenges"] = [
                        {
                            "claim_id": peer["claim_id"],
                            "claim_revision": peer["revision"],
                            "objection": PROSE,
                            "decision_impact": PROSE,
                            "candidate_test": PROSE,
                        }
                    ]
                text = json.dumps(output)
            physical.append((turn["phase"], text))
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
        headers={"Idempotency-Key": "rich-prose-full-council"},
        json={
            "provider": "nebius_token_factory",
            "review_protocol": "reviewed_v3",
            "prompt": "Compare generic approaches with explicit conditions.",
            "models": research.settings.policy["council_default_models"],
            "budget_usd": 5,
        },
    )
    assert response.is_success, response.text
    cid = response.json()["chat"]["id"]
    drain(app)
    view = client.get("/api/chats/" + cid).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert not view["review"].get("synthesis_fallback")
    assert {phase for phase, _ in physical} == {
        "opening",
        "extraction",
        "scrutiny",
        "repair",
        "recheck",
        "synthesis",
    }
    assert any(
        finding["origin"] == "peer_challenge" and finding["objection"] == PROSE
        for finding in view["review"]["findings"]
        if "origin" in finding
    )
    assert all(PROSE in claim["text"] for claim in view["review"]["claims"])
    assert all(PROSE in finding["objection"] for finding in view["review"]["findings"])
    assert len(view["review"]["admission_records"]) >= 7
    assert view["budget"]["absolute_cap_usd"] == 24
    exported = client.post(
        f"/api/chats/{cid}/review/exports",
        headers={"Idempotency-Key": "rich-prose-export"},
        json={},
    )
    assert exported.is_success, exported.text
    packed = client.get(exported.json()["download"])
    assert packed.is_success
    data = packed.content
    assert verify_review_pack(io.BytesIO(data))["reproduced"]


@pytest.mark.parametrize(
    "phase,next_phase",
    [("repair", "repair"), ("recheck", "synthesis"), ("synthesis", None)],
)
def test_completed_replies_at_later_stages_recover_without_more_inference(
    client, app, monkeypatch, phase, next_phase
):
    research, chat, call, physical = completed_rejected_reply(
        client, app, monkeypatch, phase=phase
    )
    with research.store.tx() as c:
        calls = research.store.list(c, "call", chat["mission_id"])
        financial = [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY rowid")
        ]
    result = restore_completed_review(research, call["id"])
    current = client.get("/api/chats/" + chat["id"]).json()
    assert current["chat"]["error"] is None
    assert current["chat"]["status"] == (
        "completed" if phase == "synthesis" else "paused"
    )
    if next_phase:
        assert current["next_turn"]["phase"] == next_phase
    else:
        assert current["chat"]["final_message_id"] == result["message_id"]
    assert result["new_inference_calls"] == 0 and not app.state.executor.run_once()
    assert len(physical) == len(calls)
    with research.store.tx() as c:
        assert research.store.list(c, "call", chat["mission_id"]) == calls
        assert [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY rowid")
        ] == financial


@pytest.mark.parametrize(
    "violation",
    [
        "stale_revision",
        "missing_finding",
        "own_peer",
        "invented_peer",
        "authority_extra",
    ],
)
def test_long_replies_still_obey_author_revision_reference_and_authority_checks(
    client, app, violation
):
    initial = create(client)
    research = app.state.research
    for _ in range(5):
        assert app.state.executor.run_once()
    with research.store.tx() as c:
        chat = research.store.get(c, initial["chat"]["id"], "chat")
        messages = research.chat.messages(c, chat)
        turn = research.chat.next_turn(chat, messages, c)
        snapshot = research.chat.review.snapshot(c, chat)
        before = digest(snapshot)
        output = expand_prose(
            json.loads(research.chat.review.demo(c, chat, messages, turn)), "repair"
        )
        if violation == "stale_revision":
            output["repairs"][0]["claim_revision"] = 999
        elif violation == "missing_finding":
            output["repairs"][0]["finding_ids"] = []
        elif violation == "authority_extra":
            output["human_verified"] = True
        else:
            target = next(
                claim
                for claim in snapshot["claims"]
                if claim["author_id"] == turn["author_id"]
            )
            output["peer_challenges"] = [
                {
                    "claim_id": target["claim_id"]
                    if violation == "own_peer"
                    else "invented-claim",
                    "claim_revision": target["revision"],
                    "objection": PROSE,
                    "decision_impact": PROSE,
                    "candidate_test": PROSE,
                }
            ]
        with pytest.raises(DomainError):
            research.chat.review.admit(
                c, chat, turn, json.dumps(output), "adversarial-rich-reply"
            )
        assert digest(research.chat.review.snapshot(c, chat)) == before


def test_response_safety_envelope_blocks_oversized_json_without_touching_state(
    client, app
):
    initial = create(client)
    research = app.state.research
    for _ in range(3):
        app.state.executor.run_once()
    with research.store.tx() as c:
        chat = research.store.get(c, initial["chat"]["id"], "chat")
        turn = research.chat.next_turn(chat, research.chat.messages(c, chat), c)
        before = digest(research.chat.review.snapshot(c, chat))
        with pytest.raises(DomainError, match="response safety envelope"):
            research.chat.review.admit(
                c, chat, turn, " " * (MAX_REVIEW_REPLY_BYTES + 1), "oversized-response"
            )
        assert digest(research.chat.review.snapshot(c, chat)) == before


@pytest.mark.parametrize("unsupported", ["expression", "decimal", "unit"])
def test_unsupported_optional_calculation_does_not_reject_valid_claims(
    client, app, unsupported
):
    initial = create(client)
    research = app.state.research
    for _ in range(3):
        assert app.state.executor.run_once()
    with research.store.tx() as c:
        chat = research.store.get(c, initial["chat"]["id"], "chat")
        messages = research.chat.messages(c, chat)
        turn = research.chat.next_turn(chat, messages, c)
        output = json.loads(research.chat.review.demo(c, chat, messages, turn))
        claim = output["claims"][0]
        descriptor = {
            "claim_ref": claim["ref"],
            "source_unit_ids": claim["source_unit_ids"],
            "kind": "calculation",
            "scope": "Declared source-bound calculation only",
            "expression": "2+2",
            "expected_value": "4",
        }
        if unsupported == "expression":
            descriptor["expression"] = "2+" * 300 + "2"
        elif unsupported == "decimal":
            descriptor["expected_value"] = "4." + "0" * 90
        else:
            descriptor["output_unit"] = "Unsupported described quantity " * 10
        output["audits"] = [descriptor]
        research.chat.review.admit(
            c, chat, turn, json.dumps(output), "unsupported-calculation"
        )
        snapshot = research.chat.review.snapshot(c, chat)
        assert len(snapshot["claims"]) == len(output["claims"])
        assert snapshot["audit_results"][0]["state"] == "unknown"
        assert (
            snapshot["audit_descriptors"][0]["expression"] == descriptor["expression"]
        )


def test_targeted_followup_retains_long_scope_and_supplemental_notes(
    client, app, monkeypatch
):
    original = UnifiedCouncil.demo

    def long_scope(self, c, chat, messages, turn):
        raw = original(self, c, chat, messages, turn)
        if (
            turn["phase"] == "extraction"
            and self.record(c, chat).get("route", {}).get("kind") == "delta"
        ):
            output = json.loads(raw)
            output["reason"] += PROSE
            output["notes"] = "Supplemental scope commentary"
            return json.dumps(output)
        return raw

    monkeypatch.setattr(UnifiedCouncil, "demo", long_scope)
    initial = create(client)
    cid = initial["chat"]["id"]
    drain(app)
    old = client.get("/api/chats/" + cid).json()
    response = client.post(
        f"/api/chats/{cid}/messages",
        headers={"Idempotency-Key": "rich-delta-scope"},
        json={
            "text": "Challenge this assertion within its boundary.",
            "action": "challenge",
            "claim_ids": [old["review"]["claims"][0]["claim_id"]],
        },
    )
    assert response.is_success, response.text
    drain(app)
    current = client.get("/api/chats/" + cid).json()
    assert current["chat"]["status"] == "completed", current["chat"].get("error")
    scope = next(
        message
        for message in current["messages"][len(old["messages"]) :]
        if message.get("phase") == "extraction"
    )
    assert PROSE in scope["content"]
    assert "Supplemental scope commentary" in scope["content"]
    assert current["review"]["admission_records"]
