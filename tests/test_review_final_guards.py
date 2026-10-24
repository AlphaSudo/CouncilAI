import uuid
import pytest
from test_workflow import post
from test_council_review import completed, mutate_review
from test_council_chat import drain
from test_direct_provider import direct_chat, transport
from zerowall.free_errors import FreeProviderError


def test_stale_answer_cannot_be_accepted_until_new_synthesis(client, app):
    v = completed(client, app)
    claim = v["review"]["claims"][0]
    v = mutate_review(
        client,
        v,
        "evidence",
        {
            "claim_id": claim["claim_id"],
            "claim_revision": claim["revision"],
            "content": "A source specifically about this bounded demonstration.",
            "provenance": "Permitted fixture source",
            "relation": "supports",
        },
    )
    url = f"/api/chats/{v['chat']['id']}/control"
    assert (
        client.post(
            url,
            json={"action": "accept"},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        ).status_code
        == 409
    )
    v = mutate_review(client, v, "resynthesize", {})
    drain(app)
    v = client.get("/api/chats/" + v["chat"]["id"]).json()
    assert not v["review"]["synthesis_stale"]
    assert len([m for m in v["messages"] if m["phase"] == "synthesis"]) == 2
    assert post(client, f"/chats/{v['chat']['id']}/control", {"action": "accept"})[
        "chat"
    ]["accepted"]
    with app.state.research.store.tx() as c:
        pubs = app.state.research.store.list(
            c, "review_publication", v["chat"]["mission_id"]
        )
    assert len(pubs) == 2
    assert pubs[0]["decision_hash"] != pubs[1]["decision_hash"]


def test_url_alone_does_not_become_a_checked_source(client, app):
    v = completed(client, app)
    claim = v["review"]["claims"][0]
    response = client.post(
        f"/api/chats/{v['chat']['id']}/review/evidence",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "expected_revision": v["review"]["revision"],
            "claim_id": claim["claim_id"],
            "claim_revision": claim["revision"],
            "content": "https://example.com/unread",
            "provenance": "A link is not an excerpt",
            "relation": "supports",
            "assessment_reason": "Claiming assessment cannot substitute for supplying source content.",
        },
    )
    assert response.status_code == 422


def test_unresolved_recommendation_keeps_a_direct_answer_with_computed_qualifications(
    client, app
):
    v = completed(client, app)
    claim = v["review"]["claims"][0]
    rendered = app.state.research.chat.review.render_synthesis(
        v["review"],
        {
            "blocks": [
                {
                    "section": "direct_answer",
                    "text": "Conditionally try the proposed workflow and run the stated validation before relying on it.",
                    "claim_ids": [claim["claim_id"]],
                    "evidence_ids": [],
                }
            ]
        },
    )
    assert "Conditional answer" in rendered
    assert "unresolved checks" in rendered
    assert "not a verified result" in rendered
    assert "Claim and evidence ledger" in rendered


@pytest.mark.parametrize("cost", ["0.01", -1, True])
def test_invalid_reported_cost_locks_provider_and_preserves_attempt(
    client, app, monkeypatch, cost
):
    r, seen = transport(app, monkeypatch, cost=cost)
    v = direct_chat(client, r)
    model = list(r.direct_provider.entries())[0]
    with pytest.raises(FreeProviderError, match="invalid cost"):
        r.direct_provider.call(
            v["chat"]["mission_id"], "A bounded request", model=model
        )
    assert len(seen) == 1
    with r.store.tx() as c:
        call = r.store.list(c, "call", v["chat"]["mission_id"])[0]
        assert call["state"] == "failed"
        assert call["cost_status"] == "invalid"
