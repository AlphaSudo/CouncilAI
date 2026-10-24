"""Review format faults must not erase the planned public council discussion."""

import json
from copy import deepcopy

import httpx
import pytest
from test_council_chat import drain
from test_token_factory_generation import sse
from test_token_factory_research import setup_testing
from test_unified_council import create

from zerowall.council_review_v3 import UnifiedCouncil


@pytest.mark.parametrize("fault", ["invalid_json", "ambiguous_json", "missing_claims"])
def test_second_cycle_extraction_fault_keeps_challenges_each_author_and_recheck(
    client, app, monkeypatch, fault
):
    original = UnifiedCouncil.demo
    observed = []

    def demo(self, c, chat, messages, turn):
        record = self.record(c, chat)
        if record["cycle"] != 2:
            return original(self, c, chat, messages, turn)
        observed.append((turn["phase"], turn.get("author_id")))
        if turn["phase"] == "extraction":
            if fault == "invalid_json":
                return '{"claims": [incomplete'
            if fault == "ambiguous_json":
                return '{"claims": []}\n{"claims": [{"ref":"C99"}]}'
            value = json.loads(original(self, c, chat, messages, turn))
            value["claims"] = []
            return json.dumps(value)
        if record.get("discussion_continuity"):
            raw, ids = self.prompt(c, chat, messages, turn)
            payload = json.loads(raw)
            assert "response_schema" not in payload
            assert "transport_format_rules" not in payload
            assert payload["public_messages"]
            assert all(m["id"] in ids for m in payload["public_messages"])
            assert payload["review_incomplete"] is True
            assert "Markdown" in payload["instructions"]
            if turn["phase"] == "repair":
                assert any(m["phase"] == "scrutiny" for m in payload["public_messages"])
            if turn["phase"] == "recheck":
                assert (
                    len(
                        [
                            m
                            for m in payload["public_messages"]
                            if m["phase"] == "repair"
                        ]
                    )
                    == 3
                )
            return f"Public {turn['phase']} from {turn['participant']['name']}: unverified discussion continues."
        return original(self, c, chat, messages, turn)

    monkeypatch.setattr(UnifiedCouncil, "demo", demo)
    initial = create(client, review_protocol="reviewed_v4")
    cid = initial["chat"]["id"]
    drain(app)
    before = deepcopy(client.get("/api/chats/" + cid).json()["messages"])
    response = client.post(
        "/api/chats/" + cid + "/messages",
        headers={"Idempotency-Key": "continuity-second-" + fault},
        json={"text": "Compare the designs again under a new latency constraint."},
    )
    assert response.is_success, response.text
    drain(app)
    view = client.get("/api/chats/" + cid).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    second = [
        m
        for m in view["messages"]
        if m.get("review_cycle") == 2 and m["role"] == "assistant"
    ]
    assert [m["phase"] for m in second] == [
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
    assert len(observed) == 10  # Original plan, no paid JSON repair or repeated turn.
    assert len({m["participant_id"] for m in second if m["phase"] == "repair"}) == 3
    assert not any(
        s["state"] == "skipped" for s in view["stage_results"] if s["review_cycle"] == 2
    )
    assert view["review"]["discussion_continuity"]["grants_authority"] is False
    assert not view["review"]["claims"] and not view["review"]["evidence"]
    assert view["chat"]["review_state"] == "incomplete"
    assert view["chat"]["generation_state"] == "complete"
    assert view["messages"][: len(before)] == before
    assert not app.state.executor.run_once()
    # A later healthy cycle must get its ordinary typed review back; degraded
    # mode is scoped to the failed cycle, never a lifetime chat downgrade.
    frozen = deepcopy(view["messages"])
    response = client.post(
        "/api/chats/" + cid + "/messages",
        headers={"Idempotency-Key": "continuity-third-" + fault},
        json={"text": "Compare again for a fresh maintainability constraint."},
    )
    assert response.is_success, response.text
    drain(app)
    third = client.get("/api/chats/" + cid).json()
    assert third["chat"]["status"] == "completed"
    assert not third["review"].get("discussion_continuity")
    assert third["review"]["claims"]
    assert third["messages"][: len(frozen)] == frozen


def test_missing_family_mechanism_keeps_valid_claims_and_full_review(
    client, app, monkeypatch
):
    original = UnifiedCouncil.demo

    def demo(self, c, chat, messages, turn):
        raw = original(self, c, chat, messages, turn)
        if turn["phase"] == "extraction":
            value = json.loads(raw)
            for family in value["families"]:
                family.pop("mechanism", None)
            return json.dumps(value)
        return raw

    monkeypatch.setattr(UnifiedCouncil, "demo", demo)
    initial = create(client, review_protocol="reviewed_v4")
    drain(app)
    view = client.get("/api/chats/" + initial["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed"
    assert len(view["review"]["claims"]) == 3
    assert len([m for m in view["messages"] if m["phase"] == "repair"]) == 3
    assert any(m["phase"] == "recheck" for m in view["messages"])
    assert not view["review"].get("discussion_continuity")
    assert view["review"]["quarantine"]


@pytest.mark.parametrize("failed_phase", ["extraction", "scrutiny"])
@pytest.mark.parametrize("member_count", [3, 4])
def test_provider_transport_keeps_the_original_full_schedule_without_format_retry(
    client, app, monkeypatch, failed_phase, member_count
):
    r = setup_testing(app, include_beam=True)
    selected = list(r.settings.policy["council_default_models"])
    if member_count == 4:
        selected.append(
            next(model for model in r.settings.models if "Lightning" in model)
        )
    original_client = httpx.Client
    physical = []

    def handler(request):
        body = json.loads(request.content)
        with r.store.tx() as c:
            chat = json.loads(
                c.execute(
                    "SELECT body FROM records WHERE kind='chat' ORDER BY rowid DESC LIMIT 1"
                ).fetchone()[0]
            )
            messages = r.chat.messages(c, chat)
            turn = r.chat.next_turn(chat, messages, c)
            record = r.chat.review.record(c, chat)
            phase = turn["phase"]
            physical.append((phase, turn["participant"]["id"]))
            if phase == "opening":
                text = "A reversible local queue preserves input order. This synthetic proposal is unmeasured."
            elif phase == failed_phase:
                text = 'The review is useful, but its JSON is incomplete: {"claims": ['
            elif record.get("discussion_continuity"):
                stage = json.loads(
                    body["messages"][-1]["content"].split("Current stage:\n")[-1]
                )
                assert stage["public_messages"] and "response_schema" not in stage
                assert "transport_format_rules" not in stage
                assert "response_format" not in body
                text = f"Public {phase}: compare the actual author responses; evidence remains unverified."
            else:
                text = r.chat.review.demo(c, chat, messages, turn)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=sse(body["model"], text=text),
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original_client(**kw, transport=httpx.MockTransport(handler)),
    )
    response = client.post(
        "/api/chats",
        headers={"Idempotency-Key": "http-continuity-" + failed_phase},
        json={
            "provider": "nebius_token_factory",
            "prompt": "Compare local queues under explicit constraints.",
            "models": selected,
            "budget_usd": 2,
            "review_protocol": "reviewed_v4",
        },
    )
    assert response.is_success, response.text
    drain(app)
    view = client.get("/api/chats/" + response.json()["chat"]["id"]).json()
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert [p for p, _ in physical] == ["opening"] * member_count + [
        "extraction",
        "scrutiny",
    ] + ["repair"] * member_count + ["recheck", "synthesis"]
    assert view["budget"]["attempts"] == 2 * member_count + 4
    assert all(a["state"] == "completed" for a in view["accounting"]["attempts"])
    assert len({a for p, a in physical if p == "repair"}) == member_count
    assert not view["review"]["evidence"]
    assert not app.state.executor.run_once()
