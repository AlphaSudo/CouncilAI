"""Current Council workflow tests; scripted outputs do not measure intelligence."""

import hashlib
import io
import json
import zipfile
from copy import deepcopy

import pytest
from test_council_chat import drain
from test_direct_provider import setup_direct
from test_workflow import post

from zerowall.council_review_v3 import UnifiedCouncil
from zerowall.review_exports import verify_review_pack


def create(client, **kwargs):
    return post(
        client,
        "/chats",
        {
            "prompt": "Compare generic designs within a zero additional-spend constraint.",
            "models": ["demo/analyst", "demo/critic", "demo/builder"],
            "review_protocol": "reviewed_v3",
            **kwargs,
        },
    )


def test_normal_api_uses_unified_council_and_completes_current_stages(client, app):
    initial = create(client)
    assert initial["chat"]["protocol"]["version"] == "reviewed_v3"
    assert initial["review"]["execution_plan"]["baseline_calls"] == 10
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert view["review"]["contract"]["policy_version"] == "generic-publication-v3"
    assert [m["phase"] for m in view["messages"]] == [
        "prompt",
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
    assert all(
        "Response and revision" in m["content"]
        for m in view["messages"]
        if m["phase"] == "repair"
    )
    assert view["review"]["inventory_status"] == "partial"
    assert view["review_adoption"]["available"]  # A new explicit cycle can adopt answer-first; this publication stays v3.


def test_new_cycle_retains_chat_history_and_rotates_deliberation_order(client, app):
    initial = create(client)
    cid = initial["chat"]["id"]
    drain(app)
    before = deepcopy(client.get("/api/chats/" + cid).json())
    post(
        client,
        f"/chats/{cid}/messages",
        {"text": "Now reconsider the implementation cost under the same constraints."},
    )
    drain(app)
    after = client.get("/api/chats/" + cid).json()
    assert after["chat"]["status"] == "completed", after["chat"].get("error")
    assert after["messages"][: len(before["messages"])] == before["messages"]
    orders = [
        [
            m["participant_id"]
            for m in after["messages"]
            if m["phase"] == "repair" and m["review_cycle"] == cycle
        ]
        for cycle in (1, 2)
    ]
    assert orders[0] != orders[1]


def test_late_peer_objection_gets_one_bounded_exchange_and_replays(
    client, app, monkeypatch, tmp_path
):
    original = UnifiedCouncil.demo
    injected = []

    def with_peer(self, c, chat, messages, turn):
        raw = original(self, c, chat, messages, turn)
        if (
            turn["phase"] == "repair"
            and not turn.get("focused")
            and turn["author_id"] == "member_3"
        ):
            snapshot = self.snapshot(c, chat)
            claim = next(x for x in snapshot["claims"] if x["author_id"] == "member_1")
            value = json.loads(raw)
            value["peer_challenges"] = [
                {
                    "claim_id": claim["claim_id"],
                    "claim_revision": claim["revision"],
                    "objection": "The useful scope still depends on the evaluation boundary.",
                    "decision_impact": "A broader interpretation could change the decision.",
                    "candidate_test": "Compare the stated boundary with the requested deliverable.",
                }
            ]
            injected.append(claim["claim_id"])
            return json.dumps(value)
        return raw

    monkeypatch.setattr(UnifiedCouncil, "demo", with_peer)
    initial = create(client)
    cid = initial["chat"]["id"]
    drain(app)
    view = client.get("/api/chats/" + cid).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert injected
    assert view["review"]["execution_plan"]["focused_exchange_calls"] == 2
    assert len([m for m in view["messages"] if m["phase"] == "recheck"]) == 2
    assert len([m for m in view["messages"] if m["phase"] == "repair"]) == 4
    assert view["review"]["focused_authors"] == ["member_1"]
    item = post(client, f"/chats/{cid}/review/exports", {})
    path = tmp_path / "current.zip"
    path.write_bytes(client.get(item["download"]).content)
    assert verify_review_pack(path)["format"] == "zerowall-review-v3"
    assert verify_review_pack(path)["reproduced"]


def test_daily_capacity_cannot_be_promised_to_two_oversized_queued_requests(
    client, app
):
    r = setup_direct(app)
    r.settings.direct_policy["daily_attempt_cap"] = 29
    body = {"provider": "direct_council", "models": list(r.direct_provider.entries())}
    first = create(client, **body)
    second = post(
        client,
        "/chats",
        {"prompt": "Another full council question", **body},
        status=429,
    )
    assert "remain" in second["detail"]
    with r.store.tx() as c:
        capacity = r.direct_provider.capacity(c)
        assert capacity["daily_remaining"] == 14
    post(client, f"/chats/{first['chat']['id']}/control", {"action": "stop"})
    with r.store.tx() as c:
        assert r.direct_provider.capacity(c)["daily_remaining"] == 29
        assert not r.store.list(c, "call", first["chat"]["mission_id"])


def test_legacy_v2_to_current_preserves_prior_publication_and_bytes(
    client, app, tmp_path
):
    first = create(client, review_protocol="reviewed_v2")
    cid = first["chat"]["id"]
    drain(app)
    old = deepcopy(client.get("/api/chats/" + cid).json())
    post(
        client,
        f"/chats/{cid}/messages",
        {
            "text": "Reconsider the current assumptions.",
            "review_protocol": "reviewed_v3",
        },
    )
    drain(app)
    current = client.get("/api/chats/" + cid).json()
    assert current["chat"]["status"] == "completed", current["chat"].get("error")
    assert current["messages"][: len(old["messages"])] == old["messages"]
    assert (
        current["chat"]["protocol_history"][0]["protocol_hash"]
        == old["chat"]["protocol_hash"]
    )
    item = post(client, f"/chats/{cid}/review/exports", {})
    path = tmp_path / "mixed.zip"
    path.write_bytes(client.get(item["download"]).content)
    assert verify_review_pack(path)["reproduced"]


def test_original_source_and_audit_input_tampering_are_rejected(
    client, app, monkeypatch, tmp_path
):
    original = UnifiedCouncil.demo

    def with_audit(self, c, chat, messages, turn):
        raw = original(self, c, chat, messages, turn)
        if turn["phase"] == "extraction":
            value = json.loads(raw)
            claim = value["claims"][0]
            value["audits"] = [
                {
                    "claim_ref": claim["ref"],
                    "source_unit_ids": claim["source_unit_ids"],
                    "kind": "calculation",
                    "scope": "Declared example only",
                    "expression": "2+2",
                    "expected_value": "4",
                }
            ]
            return json.dumps(value)
        return raw

    monkeypatch.setattr(UnifiedCouncil, "demo", with_audit)
    initial = create(client)
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    # Its author revision invalidates the original descriptor instead of
    # transferring a successful arithmetic result to an altered assertion.
    assert view["review"]["audit_results"][0]["state"] == "unknown"
    item = post(client, f"/chats/{initial['chat']['id']}/review/exports", {})
    path = tmp_path / "audit.zip"
    path.write_bytes(client.get(item["download"]).content)
    assert verify_review_pack(path)["reproduced"]
    with zipfile.ZipFile(io.BytesIO(path.read_bytes())) as pack:
        files = {name: pack.read(name) for name in pack.namelist()}
    snapshot = json.loads(files["review.json"])
    snapshot["audit_results"][0]["inputs"]["descriptor"]["expression"] = "2+3"
    files["review.json"] = json.dumps(snapshot).encode()
    manifest = json.loads(files["manifest.json"])
    manifest["files"]["review.json"] = hashlib.sha256(files["review.json"]).hexdigest()
    files["manifest.json"] = json.dumps(manifest).encode()
    altered = tmp_path / "altered-audit.zip"
    with zipfile.ZipFile(altered, "w") as pack:
        for name, data in files.items():
            pack.writestr(name, data)
    with pytest.raises(ValueError, match="audit inputs/results"):
        verify_review_pack(altered)


def test_explicit_claim_challenge_reviews_only_affected_scope_in_same_chat(
    client, app, tmp_path
):
    first = create(client)
    cid = first["chat"]["id"]
    drain(app)
    old = client.get("/api/chats/" + cid).json()
    claim = old["review"]["claims"][0]
    result = post(
        client,
        f"/chats/{cid}/messages",
        {
            "text": "Does this assertion really satisfy its declared boundary?",
            "action": "challenge",
            "claim_ids": [claim["claim_id"]],
        },
    )
    assert result["review"]["execution_plan"]["baseline_calls"] == 5
    drain(app)
    after = client.get("/api/chats/" + cid).json()
    assert after["chat"]["status"] == "completed", after["chat"].get("error")
    assert after["messages"][: len(old["messages"])] == old["messages"]
    new = [
        m
        for m in after["messages"]
        if m.get("review_cycle") == 2 and m["role"] == "assistant"
    ]
    assert [m["phase"] for m in new] == [
        "extraction",
        "scrutiny",
        "repair",
        "recheck",
        "synthesis",
    ]
    assert after["review"]["claims"][0]["claim_id"] == claim["claim_id"]
    item = post(client, f"/chats/{cid}/review/exports", {})
    path = tmp_path / "targeted.zip"
    path.write_bytes(client.get(item["download"]).content)
    assert verify_review_pack(path)["reproduced"]


def test_explicit_explanation_uses_one_call_without_new_evidence_status(client, app):
    initial = create(client)
    cid = initial["chat"]["id"]
    drain(app)
    before = client.get("/api/chats/" + cid).json()
    post(
        client,
        f"/chats/{cid}/messages",
        {"text": "Explain why the saved result is conditional.", "action": "explain"},
    )
    drain(app)
    after = client.get("/api/chats/" + cid).json()
    assert after["chat"]["status"] == "completed", after["chat"].get("error")
    assert after["review"]["execution_plan"]["baseline_calls"] == 1
    assert [
        {k: v for k, v in d.items() if k != "basis_hash"}
        for d in after["review"]["decisions"]
    ] == [
        {k: v for k, v in d.items() if k != "basis_hash"}
        for d in before["review"]["decisions"]
    ]
    assert len(after["messages"]) == len(before["messages"]) + 2
    assert "No new checks were performed" in after["messages"][-1]["content"]


def test_out_of_scope_targeted_challenge_expands_without_erasing_probe(
    client, app, monkeypatch
):
    original = UnifiedCouncil.demo

    def broaden(self, c, chat, messages, turn):
        raw = original(self, c, chat, messages, turn)
        if (
            turn["phase"] == "extraction"
            and self.record(c, chat).get("route", {}).get("kind") == "delta"
        ):
            value = json.loads(raw)
            value.update(
                within_claim_scope=False,
                reason="The new mechanism changes the original premise.",
            )
            return json.dumps(value)
        return raw

    monkeypatch.setattr(UnifiedCouncil, "demo", broaden)
    initial = create(client)
    cid = initial["chat"]["id"]
    drain(app)
    before = client.get("/api/chats/" + cid).json()
    post(
        client,
        f"/chats/{cid}/messages",
        {
            "text": "Consider a materially different premise.",
            "action": "challenge",
            "claim_ids": [before["review"]["claims"][0]["claim_id"]],
        },
    )
    drain(app)
    after = client.get("/api/chats/" + cid).json()
    assert after["chat"]["status"] == "completed", after["chat"].get("error")
    assert after["review"]["cycle"] == 3
    assert any("Scope expanded" in m["content"] for m in after["messages"])


def test_unavailable_critic_reassigns_a_selected_seat_inside_reserve(
    client, app, monkeypatch
):
    import httpx
    from test_review_resilience import force_due, scripted_transport

    failures = []

    def fail(payload):
        if (
            payload["phase"] == "scrutiny"
            and payload["you"].get("provider") == "nvidia_nim"
        ):
            failures.append(True)
            return httpx.Response(
                503, headers={"Retry-After": "1"}, json={"error": {"code": 503}}
            )

    r, seen = scripted_transport(app, monkeypatch, fail)
    initial = create(
        client, provider="direct_council", models=list(r.direct_provider.entries())
    )
    cid = initial["chat"]["id"]
    for _ in range(5):
        drain(app)
        if client.get("/api/chats/" + cid).json()["chat"]["status"] != "waiting":
            break
        force_due(r)
    after = client.get("/api/chats/" + cid).json()
    assert after["chat"]["status"] == "completed", after["chat"].get("error")
    assert len(failures) == 2
    assert after["budget"]["attempts"] == 14
    changes = after["review"]["reassignments"]
    assert any(
        x["actor"] == "bounded_selected_seat_recovery" and x["phase"] == "scrutiny"
        for x in changes
    )
    assert len([x for x in seen if x["phase"] == "opening"]) == 4


def test_bounded_rationale_does_not_fail_only_for_legacy_cosmetic_limits(
    client, app, monkeypatch
):
    original = UnifiedCouncil.demo
    long_method = "A scoped method with all relevant qualifications preserved. " * 7

    def longer(self, c, chat, messages, turn):
        raw = original(self, c, chat, messages, turn)
        if turn["phase"] == "scrutiny":
            value = json.loads(raw)
            value["findings"][0]["test"]["method"] = long_method
            return json.dumps(value)
        return raw

    monkeypatch.setattr(UnifiedCouncil, "demo", longer)
    initial = create(client)
    drain(app)
    after = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert after["chat"]["status"] == "completed", after["chat"].get("error")
    assert after["review"]["findings"][0]["test"]["method"] == long_method


def test_new_material_recheck_issue_is_promoted_and_answered_before_closure(
    client, app, monkeypatch
):
    original = UnifiedCouncil.demo

    def issue(self, c, chat, messages, turn):
        raw = original(self, c, chat, messages, turn)
        if turn["phase"] == "recheck" and not turn.get("focused"):
            value = json.loads(raw)
            value["assessments"][0]["concerns"] = [
                {
                    "kind": "new_issue",
                    "detail": "The scope needs a further explicit boundary.",
                    "affected_scope": "The current assertion",
                    "materiality": "decision_changing",
                }
            ]
            return json.dumps(value)
        return raw

    monkeypatch.setattr(UnifiedCouncil, "demo", issue)
    initial = create(client)
    drain(app)
    after = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert after["chat"]["status"] == "completed", after["chat"].get("error")
    promoted = [
        f for f in after["review"]["findings"] if f.get("origin") == "recheck_concern"
    ]
    assert len(promoted) == 1
    assert any(
        promoted[0]["id"] in r["finding_ids"] for r in after["review"]["repairs"]
    )
    assert len([m for m in after["messages"] if m["phase"] == "recheck"]) == 2


def test_no_budget_leaves_late_peer_issue_open_instead_of_faking_closure(
    client, app, monkeypatch
):
    from zerowall.db import DomainError

    original = UnifiedCouncil.demo

    def issue(self, c, chat, messages, turn):
        raw = original(self, c, chat, messages, turn)
        if turn["phase"] == "recheck":
            value = json.loads(raw)
            value["assessments"][0]["concerns"] = [
                {
                    "kind": "new_issue",
                    "detail": "An unresolved budget boundary can change the answer.",
                    "affected_scope": "The current assertion",
                    "materiality": "decision_changing",
                }
            ]
            return json.dumps(value)
        return raw

    def deny(*args):
        raise DomainError("No daily capacity for another exchange", 429)

    monkeypatch.setattr(UnifiedCouncil, "demo", issue)
    monkeypatch.setattr(app.state.research.chat.runtime, "expand", deny)
    initial = create(client)
    drain(app)
    after = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert after["chat"]["status"] == "completed", after["chat"].get("error")
    assert not after["review"]["focused_authors"]
    assert "omitted" in after["review"]["focus_decision"]["reason"]
    assert any(d["permission"] == "unresolved" for d in after["review"]["decisions"])


def test_source_context_is_frozen_for_openings_and_never_auto_promoted(client, app):
    initial = create(
        client,
        review_options={
            "sources": [
                {
                    "id": "brief",
                    "text": "A supplied example, not an observed measurement.",
                    "provenance": "Authored fixture context",
                }
            ]
        },
    )
    r = app.state.research
    with r.store.tx() as c:
        chat = r.store.get(c, initial["chat"]["id"], "chat")
        turn = r.chat.next_turn(chat, r.chat.messages(c, chat), c)
        prompt, _ = r.chat.prompt(chat, r.chat.messages(c, chat), turn, c)
        assert json.loads(prompt)["contract"]["options"]["sources"][0]["id"] == "brief"
    drain(app)
    after = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert not after["review"]["evidence"]
    assert all(d["permission"] != "supported" for d in after["review"]["decisions"])


def test_racing_admissions_cannot_reserve_the_same_daily_capacity(app):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from zerowall.contracts import ChatCreate
    from zerowall.db import DomainError

    r = setup_direct(app)
    r.settings.direct_policy["daily_attempt_cap"] = 29
    barrier = Barrier(2)

    def submit():
        body = ChatCreate(
            prompt="A bounded current council question.",
            provider="direct_council",
            models=list(r.direct_provider.entries()),
        )
        barrier.wait()
        try:
            with r.store.tx() as c:
                r.chat.create(c, body)
            return 200
        except DomainError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(), range(2)))
    assert sorted(results) == [200, 429]
    with r.store.tx() as c:
        assert r.direct_provider.capacity(c)["daily_remaining"] == 14
