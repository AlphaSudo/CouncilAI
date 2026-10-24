"""Real provider code against synthetic HTTP/SSE, including settlement/crash boundaries."""

import io
import json
import zipfile

import httpx
import pytest
from test_council_chat import drain
from test_token_factory_generation import sse
from test_token_factory_research import setup_testing

from zerowall.answer_delivery import AnswerDelivery
from zerowall.db import digest
from zerowall.review_exports import export_review, verify_review_pack


def setup(client, app, monkeypatch, mode="normal"):
    r = setup_testing(app, include_beam=True)
    original = httpx.Client
    physical = []

    def handler(request):
        body = json.loads(request.content)
        with r.store.tx() as c:
            chat = r.store.list(
                c,
                "chat",
                next(
                    iter(
                        [
                            row[0]
                            for row in c.execute(
                                "SELECT mission_id FROM records WHERE kind='chat'"
                            )
                        ]
                    )
                ),
            )[0]
            turn = r.chat.next_turn(chat, r.chat.messages(c, chat), c)
            if mode == "lead_fails" and turn["phase"] == "synthesis":
                physical.append(body)
                return httpx.Response(
                    503, json={"error": "Synthetic provider unavailable"}
                )
            if mode == "no_answer" and len(physical) == 0:
                text = ""
            elif turn["phase"] == "synthesis":
                text = "Prefer a reversible pilot under the stated constraints. This synthetic reply is not scientific evidence."
            elif turn["phase"] == "opening":
                text = "A bounded reversible engineering pilot permits learning before scale. This is a synthetic proposal, not an executed measurement."
            else:
                text = r.chat.review.demo(c, chat, r.chat.messages(c, chat), turn)
            if turn["phase"] == "opening":
                text = "A bounded reversible engineering pilot permits learning before scale. This is a synthetic proposal, not an executed measurement."
        physical.append(body)
        if mode == "first_unknown" and len(physical) == 1:
            raise httpx.RemoteProtocolError(
                "Server disconnected without sending a response."
            )
        if mode == "unknown" and len(physical) == 2:
            raise httpx.ReadTimeout("Synthetic timeout after dispatch")
        if mode == "no_answer" and len(physical) == 1:
            text = ""
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
        headers={"Idempotency-Key": "answer-first-provider-" + mode},
        json={
            "provider": "nebius_token_factory",
            "models": r.settings.policy["council_default_models"],
            "prompt": "Compare engineering pilots with a zero additional-spend requirement.",
            "budget_usd": 24,
            "spending_scope": "shared_existing_credit",
            "review_protocol": "reviewed_v4",
        },
    )
    assert response.is_success, response.text
    return r, response.json()["chat"]["id"], physical


def test_exact_receipt_recovers_crash_before_message_commit_with_no_charge_change(
    client, app, monkeypatch
):
    r, cid, physical = setup(client, app, monkeypatch)
    original = AnswerDelivery.commit

    def crash(*args, **kwargs):
        raise SystemExit("Synthetic crash after receipt settlement")

    monkeypatch.setattr(AnswerDelivery, "commit", crash)
    with pytest.raises(SystemExit):
        app.state.executor.run_once()
    with r.store.tx() as c:
        money = [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY id")
        ]
        calls = digest(
            r.store.list(c, "call", r.store.get(c, cid, "chat")["mission_id"])
        )
    monkeypatch.setattr(AnswerDelivery, "commit", original)
    r.store.recover()
    assert AnswerDelivery(r.chat).reconcile() == 1
    assert AnswerDelivery(r.chat).reconcile() == 0
    with r.store.tx() as c:
        assert [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY id")
        ] == money
        assert (
            digest(r.store.list(c, "call", r.store.get(c, cid, "chat")["mission_id"]))
            == calls
        )
    assert len(physical) == 1
    drain(app)
    assert client.get("/api/chats/" + cid).json()["chat"]["status"] == "completed"


@pytest.mark.parametrize(
    "mode", ["lead_fails", "no_answer", "unknown", "first_unknown"]
)
def test_provider_failure_retains_actual_answers_and_unknown_holds(
    client, app, monkeypatch, mode
):
    _r, cid, physical = setup(client, app, monkeypatch, mode)
    drain(app)
    view = client.get("/api/chats/" + cid).json()
    if mode in ("unknown", "first_unknown"):
        assert view["chat"]["status"] == "paused", view["chat"].get("error")
        assert len(physical) == (2 if mode == "unknown" else 1)
        assert view["budget"]["unknown_usd"] > 0
        assert view["chat"]["pending_request_recovery"]["call_id"]
        assert not any(m.get("source") == "local_partial" for m in view["messages"])
        assert (
            view["next_turn"]["key"]
            == view["chat"]["pending_request_recovery"]["turn_key"]
        )
        assert view["model_recovery"] and view["model_recovery"]["allowed"]
        assert not app.state.executor.run_once()
        return
    assert view["chat"]["status"] == "completed", view["chat"].get("error")
    assert any(m["role"] == "assistant" and m["content"] for m in view["messages"])
    if mode == "no_answer":
        first = next(s for s in view["stage_results"] if s["phase"] == "opening")
        assert first["generation_state"] == "unavailable"
    if mode == "lead_fails":
        assert view["messages"][-1]["source"] == "local_partial"
        assert view["chat"]["generation_state"] == "partial"
    assert not app.state.executor.run_once()


def test_finishing_hold_is_not_an_attempt_or_spent_usage_and_export_replays(
    client, app, monkeypatch, tmp_path
):
    r, cid, physical = setup(client, app, monkeypatch)
    for _ in range(4):
        app.state.executor.run_once()
    mid = client.get("/api/chats/" + cid).json()
    assert mid["budget"]["attempts"] == len(physical) == 4
    with r.store.tx() as c:
        holds = r.store.list(c, "finishing_reserve", mid["chat"]["mission_id"])
        assert len(holds) == 1 and holds[0]["context_tokens"] == 262144
        assert mid["accounting"]["total"]["attempts"] == 4
    drain(app)
    with r.store.tx() as c:
        chat = r.store.get(c, cid, "chat")
        assert r.budget.summary(c, chat["mission_id"])["reserved_usd"] == 0
        pack = export_review(r, c, chat)
    path = tmp_path / "answer-first.zip"
    path.write_bytes(pack)
    assert verify_review_pack(path)["reproduced"] is True
    with zipfile.ZipFile(io.BytesIO(pack)) as zipped:
        records = json.loads(zipped.read("records.json"))
        assert records["stage_result"] and records["answer_delivery"]


def test_optional_review_cannot_spend_the_final_reserve(client, app, monkeypatch):
    from zerowall.db import DomainError

    r, cid, physical = setup(client, app, monkeypatch)
    original = r.provider.call

    def unavailable_optional(*args, **kwargs):
        if kwargs.get("purpose", "").endswith(":extraction"):
            raise DomainError("Optional review does not fit remaining credit", 402)
        return original(*args, **kwargs)

    monkeypatch.setattr(r.provider, "call", unavailable_optional)
    drain(app)
    view = client.get("/api/chats/" + cid).json()
    assert view["chat"]["status"] == "completed"
    assert view["messages"][-1]["role"] == "assistant"
    assert view["messages"][-1]["phase"] == "synthesis"
    assert len(physical) == 4
    assert view["budget"]["reserved_usd"] == 0


def test_public_replay_cursor_is_bounded_and_cannot_read_another_chat(
    client, app, monkeypatch
):
    r, cid, physical = setup(client, app, monkeypatch)
    app.state.executor.run_once()
    with r.store.tx() as c:
        chat = r.store.get(c, cid, "chat")
        call_id = r.store.list(c, "call", chat["mission_id"])[0]["id"]
    response = client.get(f"/api/chats/{cid}/streams/{call_id}?limit=1")
    assert response.is_success, response.text
    first = response.json()
    assert len(first["chunks"]) <= 1 and first["next_seq"] == 1
    assert not client.get(f"/api/chats/{cid}/streams/{call_id}?limit=65").is_success
    assert (
        client.get(f"/api/chats/{cid}/streams/{call_id}?after=1").json()["chunks"] == []
    )
    other = client.post(
        "/api/chats",
        headers={"Idempotency-Key": "another-council-for-stream-guard"},
        json={
            "prompt": "A separate user's question in this local workspace.",
            "models": ["demo/analyst", "demo/critic"],
            "provider": "fixture",
        },
    ).json()
    assert (
        client.get(f"/api/chats/{other['chat']['id']}/streams/{call_id}").status_code
        == 404
    )
    assert len(physical) == 1
