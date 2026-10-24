"""Exercise every structured phase through the actual direct transport and durable queue."""

import json
import httpx
import pytest
from zerowall.db import DomainError
from test_direct_provider import setup_direct, direct_chat
from test_council_chat import drain
from test_council_review import create_review, completed
from test_workflow import post


def scripted_transport(app, monkeypatch, failure=None):
    r = setup_direct(app)
    seen = []
    original = httpx.Client

    def handler(request):
        body = json.loads(request.content)
        prompt = (
            body["contents"][0]["parts"][0]["text"]
            if "contents" in body
            else body["messages"][-1]["content"]
        )
        payload = json.loads(prompt)
        seen.append(payload)
        with r.store.tx() as c:
            row = c.execute(
                "SELECT body FROM records WHERE kind='chat' ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            chat = json.loads(row[0])
            messages = r.chat.messages(c, chat)
            turn = r.chat.next_turn(chat, messages, c)
            if failure:
                failed = failure(payload)
                if failed is not None:
                    return failed
            if turn["phase"] == "opening":
                content = "A conditional generic proposal for this task. Its real-world value has not been checked."
            else:
                content = r.chat.review.demo(c, chat, messages, turn)
        if "contents" in body:
            model = request.url.path.split("/models/")[1].split(":")[0]
            raw = {
                "modelVersion": model,
                "candidates": [
                    {"content": {"parts": [{"text": content}]}, "finishReason": "STOP"}
                ],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 10},
            }
        else:
            raw = {
                "model": body["model"],
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            }
        return httpx.Response(200, json=raw)

    monkeypatch.setattr(
        "zerowall.direct_provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    return r, seen


def force_due(r):
    with r.store.tx() as c:
        c.execute("UPDATE jobs SET body='{}' WHERE state='queued'")
        for provider in r.settings.direct_keys:
            r.store.set_setting(c, "direct_backoff:" + provider, "")


@pytest.mark.parametrize(
    "phase", ["extraction", "scrutiny", "repair", "recheck", "synthesis"]
)
def test_every_review_phase_retries_durably_without_regenerating_openings(
    client, app, monkeypatch, phase
):
    failures = []

    def failure(payload):
        if payload["phase"] == phase and not failures:
            failures.append(True)
            return httpx.Response(
                429, headers={"Retry-After": "2"}, json={"error": {"code": 429}}
            )

    r, seen = scripted_transport(app, monkeypatch, failure)
    v = direct_chat(client, r, "reviewed")
    cid = v["chat"]["id"]
    drain(app)
    v = client.get("/api/chats/" + cid).json()
    assert v["chat"]["status"] == "waiting"
    assert not app.state.executor.run_once()
    force_due(r)
    drain(app)
    v = client.get("/api/chats/" + cid).json()
    assert v["chat"]["status"] == "completed", v["chat"].get("error")
    assert v["budget"]["attempts"] == 13
    assert v["chat"]["retry_used"] == 1
    assert len([p for p in seen if p["phase"] == "opening"]) == 4
    assert len(v["review"]["claims"]) == 4


def test_failed_reviewer_requires_explicit_attributed_reassignment(
    client, app, monkeypatch
):
    r, seen = scripted_transport(
        app,
        monkeypatch,
        lambda p: (
            httpx.Response(404, json={"error": {"message": "Missing selected model"}})
            if p["phase"] == "scrutiny" and p["you"]["provider"] == "groq"
            else None
        ),
    )
    v = direct_chat(client, r, "reviewed")
    cid = v["chat"]["id"]
    drain(app)
    v = client.get("/api/chats/" + cid).json()
    assert v["chat"]["status"] == "unavailable"
    assert len(v["messages"]) == 6  # Prompt, four openings and extraction.
    target = next(p for p in v["active_members"] if p["provider"] == "gemini")
    v = post(
        client,
        f"/chats/{cid}/review/reassignments",
        {
            "expected_revision": v["review"]["revision"],
            "phase": "scrutiny",
            "participant_id": target["id"],
            "reason": "Explicit reassignment to an originally selected available member.",
        },
    )
    assert v["review"]["roles"]["scrutiny"] == target["id"]
    post(client, f"/chats/{cid}/control", {"action": "resume"})
    drain(app)
    v = client.get("/api/chats/" + cid).json()
    assert v["chat"]["status"] == "completed", v["chat"].get("error")
    assert v["messages"][-1]["partial"]
    assert len([m for m in v["messages"] if m["phase"] == "repair"]) == 3
    assert v["review"]["reassignments"][0]["actor"] == "human_director"


def test_rejected_batch_rolls_back_even_if_caller_catches_inside_transaction(
    client, app
):
    v = create_review(client)
    for _ in range(3):
        app.state.executor.run_once()
    r = app.state.research
    with r.store.tx() as c:
        chat = r.store.get(c, v["chat"]["id"], "chat")
        messages = r.chat.messages(c, chat)
        turn = r.chat.next_turn(chat, messages, c)
        output = json.loads(r.chat.review.demo(c, chat, messages, turn))
        output["claims"][-1]["quote"] = "Invented source quotation."
        with pytest.raises(DomainError):
            r.chat.review.admit(
                c, chat, turn, json.dumps(output), "diagnostic-rollback-test"
            )
    with r.store.tx() as c:
        assert r.chat.review.snapshot(c, chat)["claims"] == []


def test_long_required_context_holds_instead_of_dropping_objections(client, app):
    v = completed(client, app)
    r = app.state.research
    with r.store.tx() as c:
        chat = r.store.get(c, v["chat"]["id"], "chat")
        review = r.chat.review.record(c, chat)
        for _ in range(15):
            r.chat.message(
                c,
                chat,
                role="user",
                content="required context " * 500,
                phase="intervention",
                review_cycle=review["cycle"],
            )
        turn = r.chat.review.schedule(chat, review)[-1]
        with pytest.raises(DomainError, match="no mandatory objection was dropped"):
            r.chat.review.prompt(c, chat, r.chat.messages(c, chat), turn)


def test_source_unit_selection_is_verbatim_and_has_no_storage_id_ambiguity(client, app):
    v = create_review(client)
    for _ in range(3):
        app.state.executor.run_once()
    r = app.state.research
    with r.store.tx() as c:
        chat = r.store.get(c, v["chat"]["id"], "chat")
        messages = r.chat.messages(c, chat)
        turn = r.chat.next_turn(chat, messages, c)
        payload = json.loads(r.chat.review.prompt(c, chat, messages, turn)[0])
        output = json.loads(r.chat.review.demo(c, chat, messages, turn))
        for claim in output["claims"]:
            unit = next(
                u
                for u in payload["source_units"]
                if u["message_id"] == claim["source_message_id"]
            )
            claim.update(source_unit_id=unit["id"], quote="")
        r.chat.review.admit(
            c, chat, turn, json.dumps(output), "test-source-unit-message"
        )
        snapshot = r.chat.review.snapshot(c, chat)
        assert len(snapshot["claims"]) == 3
        for claim in snapshot["claims"]:
            source = next(m for m in messages if m["id"] == claim["source_message_id"])
            span = claim["source_span"]
            assert source["content"][span["start"] : span["end"]] == claim["text"]
        # Actual scrutiny prompts expose logical claim IDs and no competing storage IDs.
        turn = {"phase": "scrutiny", "participant": chat["participants"][1]}
        payload = json.loads(r.chat.review.prompt(c, chat, messages, turn)[0])
        assert all("id" not in x and "claim_id" in x for x in payload["claims"])
