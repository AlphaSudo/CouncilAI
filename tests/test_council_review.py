import io
import json
import zipfile
from copy import deepcopy
import pytest
from zerowall.review_policy import publication_decisions
from zerowall.review_exports import verify_review_pack
from test_workflow import post
from test_council_chat import drain


def create_review(client, models=None):
    return post(
        client,
        "/chats",
        {
            "prompt": "Compare two software designs while preserving the explicit zero-spend constraint.",
            "provider": "fixture",
            "models": models or ["demo/analyst", "demo/critic", "demo/builder"],
            "mode": "reviewed",
            "review_protocol": "reviewed_v1",
            "max_rounds": 1,
        },
    )


def test_preview_uses_the_execution_schedule_and_role_assignments(client, app):
    models = ["demo/analyst", "demo/critic", "demo/builder"]
    preview = client.get("/api/chats/preview", params={"provider": "fixture", "mode": "reviewed", "models": ",".join(models), "max_rounds": 1}).json()
    v = create_review(client, models)
    assert preview["planned_calls"] == v["remaining_planned_calls"] == 10
    assert preview["required_start"] == 13
    names = {p["id"]: p["name"] for p in v["chat"]["participants"]}
    assert preview["role_names"] == {phase: names[member] for phase, member in v["review"]["roles"].items()}
    assert not preview["blocked"]


def completed(client, app):
    cid = create_review(client)["chat"]["id"]
    drain(app)
    v = client.get("/api/chats/" + cid).json()
    assert v["chat"]["status"] == "completed", v["chat"].get("error")
    return v


def mutate_review(client, v, action, body):
    return post(
        client,
        f"/chats/{v['chat']['id']}/review/{action}",
        {"expected_revision": v["review"]["revision"], **body},
    )


def test_reviewed_cycle_is_durable_attributed_and_not_a_verification_claim(client, app):
    v = completed(client, app)
    phases = [m["phase"] for m in v["messages"]]
    assert phases == [
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
    assert len(v["review"]["claim_history"]) == 6
    assert all(c["revision"] == 2 for c in v["review"]["claims"])
    assert all(d["permission"] == "unresolved" for d in v["review"]["decisions"])
    assert v["budget"]["attempts"] == 0
    assert not v["chat"]["accepted"]
    assert v["remaining_planned_calls"] == 0
    assert "Claim and evidence ledger" in v["messages"][-1]["content"]
    with app.state.research.store.tx() as c:
        for message in v["messages"]:
            if message["phase"] == "opening":
                turn = {"phase": "opening", "participant": v["chat"]["participants"][0]}
                prompt, _ = app.state.research.chat.review.prompt(
                    c, v["chat"], v["messages"], turn
                )
                assert "findings" not in json.loads(prompt)
                assert "openings" not in json.loads(prompt)


@pytest.mark.parametrize(
    "models",
    [["demo/analyst", "demo/critic"], ["demo/analyst", "demo/critic", "demo/builder"]],
)
def test_review_schedule_count_matches_preflight(client, app, models):
    v = create_review(client, models)
    assert v["remaining_planned_calls"] == 2 * len(models) + 4
    drain(app)
    assert (
        client.get("/api/chats/" + v["chat"]["id"]).json()["chat"]["status"]
        == "completed"
    )


def test_evidence_is_scoped_human_assessed_and_old_support_does_not_transfer(
    client, app
):
    v = completed(client, app)
    claim = v["review"]["claims"][0]
    # The director rebuts an incorrect critic. This alone does not manufacture evidence.
    finding = v["review"]["findings"][0]
    v = mutate_review(
        client,
        v,
        "dispositions",
        {
            "finding_id": finding["id"],
            "status": "rebutted",
            "reason": "The criticism concerns a broader claim than the recorded demonstration.",
            "evidence_ids": [],
        },
    )
    assert v["review"]["decisions"][0]["permission"] == "conditional"
    assert v["review"]["synthesis_stale"]
    v = mutate_review(
        client,
        v,
        "evidence",
        {
            "claim_id": claim["claim_id"],
            "claim_revision": claim["revision"],
            "content": "A local workflow demonstration is a demonstration of the workflow only.",
            "provenance": "Director-provided scoped example",
            "relation": "supports",
            "assessment_reason": "I checked this source against the narrow workflow-only claim; it does not establish answer quality.",
        },
    )
    assert v["review"]["decisions"][0]["permission"] == "supported"
    assert "human assessment" in v["review"]["decisions"][0]["label"]
    changed = deepcopy(v["review"])
    changed["claims"][0]["revision"] += 1
    assert publication_decisions(changed)[0]["permission"] != "supported"


def test_unassessed_source_and_fixture_cannot_certify_a_claim(client, app):
    v = completed(client, app)
    claim = v["review"]["claims"][0]
    v = mutate_review(
        client,
        v,
        "evidence",
        {
            "claim_id": claim["claim_id"],
            "claim_revision": claim["revision"],
            "content": "This is an attributed source, not a relevance assessment.",
            "provenance": "Supplied document",
            "relation": "supports",
        },
    )
    assert v["review"]["decisions"][0]["permission"] != "supported"
    e = v["review"]["evidence"][0]
    e.update(
        origin="fixture",
        assessment_reason="I assessed this fixture but it remains a fixture.",
    )
    assert publication_decisions(v["review"])[0]["permission"] != "supported"


def test_foreign_claims_forged_authority_stale_revisions_and_invalid_dispositions_are_rejected(
    client, app
):
    v = completed(client, app)
    other = completed(client, app)
    claim = other["review"]["claims"][0]
    base = {
        "expected_revision": v["review"]["revision"],
        "claim_id": claim["claim_id"],
        "claim_revision": 2,
        "content": "An unrelated source",
        "provenance": "Test source",
        "relation": "supports",
    }
    import uuid

    url = f"/api/chats/{v['chat']['id']}/review/evidence"
    assert (
        client.post(
            url, json=base, headers={"Idempotency-Key": str(uuid.uuid4())}
        ).status_code
        == 422
    )
    assert (
        client.post(
            url,
            json={**base, "verified": True},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        ).status_code
        == 422
    )
    result = client.post(
        f"/api/chats/{v['chat']['id']}/review/dispositions",
        json={
            "expected_revision": v["review"]["revision"],
            "finding_id": v["review"]["findings"][0]["id"],
            "status": "confirmed_defect",
            "reason": "The allegation lacks attached evidence and cannot be confirmed.",
            "evidence_ids": [],
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert result.status_code == 422


def test_claim_extraction_rejects_invented_quotes_transactionally(
    client, app, monkeypatch
):
    review = app.state.research.chat.review
    original = review.demo

    def bad(c, chat, messages, turn):
        out = original(c, chat, messages, turn)
        if turn["phase"] == "extraction":
            data = json.loads(out)
            data["claims"][-1]["quote"] = (
                "Invented statement absent from the actual opening."
            )
            out = json.dumps(data)
        return out

    monkeypatch.setattr(review, "demo", bad)
    cid = create_review(client)["chat"]["id"]
    drain(app)
    v = client.get("/api/chats/" + cid).json()
    assert v["chat"]["status"] == "failed"
    assert len(v["review"]["claims"]) == 0  # Earlier valid items rolled back too.
    assert len([m for m in v["messages"] if m["phase"] == "opening"]) == 3


@pytest.mark.parametrize(
    "error", ["schema", "unknown_reference", "unsupported_section"]
)
def test_bad_synthesis_has_a_local_fallback_without_an_extra_call(
    client, app, monkeypatch, error
):
    review = app.state.research.chat.review
    original = review.demo

    def bad(c, chat, messages, turn):
        out = original(c, chat, messages, turn)
        if turn["phase"] == "synthesis":
            if error == "schema":
                return "not valid JSON"
            data = json.loads(out)
            if error == "unknown_reference":
                data["blocks"][0]["claim_ids"] = ["invented_claim"]
            else:
                data["blocks"][0]["section"] = "supported"
            return json.dumps(data)
        return out

    monkeypatch.setattr(review, "demo", bad)
    v = completed(client, app)
    assert v["review"]["synthesis_fallback"]
    assert "local summary" in v["messages"][-1]["content"]
    assert len([m for m in v["messages"] if m["phase"] == "synthesis"]) == 1


def test_review_pack_reconstructs_without_keys_and_detects_tampering(
    client, app, tmp_path
):
    v = completed(client, app)
    item = post(client, f"/chats/{v['chat']['id']}/review/exports", {})
    raw = client.get(item["download"]).content
    path = tmp_path / "review.zip"
    path.write_bytes(raw)
    assert verify_review_pack(path)["reproduced"]
    with zipfile.ZipFile(io.BytesIO(raw)) as pack:
        names = pack.namelist()
        files = {n: pack.read(n) for n in names}
    assert all(b"test-key-never-network" not in value for value in files.values())
    files["review.json"] = files["review.json"].replace(b"Unresolved", b"Confirmed")
    with zipfile.ZipFile(path, "w") as pack:
        for name, value in files.items():
            pack.writestr(name, value)
    with pytest.raises(ValueError, match="integrity"):
        verify_review_pack(path)


def test_new_contract_keeps_old_cycles_and_requires_idle_state(client, app):
    v = create_review(client)
    import uuid

    response = client.post(
        f"/api/chats/{v['chat']['id']}/review/contracts",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "expected_revision": v["review"]["revision"],
            "question": "A different scope",
            "options": {},
        },
    )
    assert response.status_code == 409
    drain(app)
    v = client.get("/api/chats/" + v["chat"]["id"]).json()
    v = mutate_review(
        client,
        v,
        "contracts",
        {
            "question": "Now compare the implementation effort under an explicit budget.",
            "options": {"constraints": [{"text": "No paid services", "kind": "hard"}]},
        },
    )
    assert v["review"]["cycle"] == 2
    assert v["review"]["history"][0]["cycle"] == 1
    assert v["review"]["claims"] == []
    drain(app)
    v = client.get("/api/chats/" + v["chat"]["id"]).json()
    assert v["chat"]["status"] == "completed"
    assert len([m for m in v["messages"] if m["phase"] == "synthesis"]) == 2


def test_early_review_finish_is_partial_and_does_not_invent_claims(client, app):
    v = create_review(client)
    app.state.executor.run_once()
    v = post(client, f"/chats/{v['chat']['id']}/control", {"action": "finish"})
    drain(app)
    v = client.get("/api/chats/" + v["chat"]["id"]).json()
    assert v["chat"]["status"] == "completed"
    assert v["messages"][-1]["partial"]
    assert v["review"]["claims"] == []
    assert "No structured claims" in v["messages"][-1]["content"]


def test_openrouter_is_disabled_in_real_configuration_and_discussion_is_unchanged(
    client, app
):
    app.state.research.settings.openrouter_enabled = False
    import uuid

    response = client.post(
        "/api/chats",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "prompt": "Do not send this to OpenRouter",
            "provider": "openrouter_free",
            "models": [
                "nvidia/nemotron-3-super-120b-a12b:free",
                "xingchen-agi/xing4.0-29b-a4b:free",
            ],
        },
    )
    assert response.status_code == 412
    assert client.get("/api/chats/availability").json()["known"] is False
