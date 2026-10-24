import json
from copy import deepcopy

import httpx
import pytest
from test_token_factory_research import setup_testing

from zerowall.db import DomainError, digest
from zerowall.output_recovery import join_draft


def failed_opening(
    client, app, monkeypatch, *, draft="", reasoning=12000, with_source=False
):
    r = setup_testing(app)
    original, requests = httpx.Client, []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if body["model"] == "zai-org/GLM-5.3-Flash":
            first = sum(x["model"] == body["model"] for x in requests) == 1
            content = draft if first else "The remaining conclusion is complete."
            finish, output = ("length", 12000) if first else ("stop", 40)
        else:
            content, finish, output, first = (
                "A complete independent opening.",
                "stop",
                40,
                False,
            )
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [
                    {
                        "finish_reason": finish,
                        "message": {
                            "content": content,
                            "reasoning_content": "PRIVATE_REASONING_MUST_NOT_BE_REPLAYED",
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": output,
                    "completion_tokens_details": {
                        "reasoning_tokens": reasoning if first else 10
                    },
                },
            },
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    response = client.post(
        "/api/chats",
        headers={"Idempotency-Key": "truncated-output"},
        json={
            "prompt": "Compare generic engineering options with clear assumptions.",
            "provider": "nebius_token_factory",
            "review_protocol": "reviewed_v3",
            "models": r.settings.models,
            "budget_usd": 1,
            "defer_start": with_source,
        },
    )
    assert response.is_success, response.text
    cid = response.json()["chat"]["id"]
    if with_source:
        r.library.ingest(
            response.json()["chat"],
            b"Saved source context for a bounded comparison.",
            title="Saved source",
        )
        resumed = client.post(
            f"/api/chats/{cid}/control",
            headers={"Idempotency-Key": "start-with-source"},
            json={"action": "resume"},
        )
        assert resumed.is_success, resumed.text
    assert app.state.executor.run_once()
    assert app.state.executor.run_once()
    view = client.get("/api/chats/" + cid).json()
    assert view["chat"]["status"] == "failed", view["chat"].get("error")
    return r, view, requests


def recover(client, view):
    return client.post(
        f"/api/chats/{view['chat']['id']}/control",
        headers={"Idempotency-Key": "recover-" + view["output_recovery"]["call_id"]},
        json={
            "action": "recover_output",
            "recovery_call_id": view["output_recovery"]["call_id"],
        },
    )


def test_reasoning_only_failure_has_counts_and_an_explicit_answer_now_request(
    client, app, monkeypatch
):
    r, failed, requests = failed_opening(client, app, monkeypatch)
    recovery = failed["output_recovery"]
    assert recovery["reasoning_tokens"] == 12000 and recovery["answer_tokens"] == 0
    assert recovery["action_label"] == "Answer now"
    assert (
        not recovery["has_saved_answer"]
        and recovery["internal_reasoning_resumable"] is False
    )
    assert len(requests) == 2
    assert not app.state.executor.run_once()  # Loading the error view never retries.
    saved_opening = deepcopy(failed["messages"][1])
    with r.store.tx() as c:
        previous = r.store.get(c, recovery["call_id"], "call")
        previous_hash = digest(previous)
        previous_request = r.chat.output_recovery.artifact(c, previous)["request"]
    response = recover(client, failed)
    assert response.is_success, response.text
    assert len(requests) == 2  # The control queues work; it does not hide a dispatch.
    assert app.state.executor.run_once()
    latest = client.get("/api/chats/" + failed["chat"]["id"]).json()
    assert len(requests) == 3
    assert requests[-1]["max_completion_tokens"] == 32768
    assert requests[-1]["reasoning_effort"] == "low"
    assert (
        requests[-1]["messages"][0]["content"].count(
            "Reasoning budget for this request:"
        )
        == 1
    )
    assert "at most 1,000 reasoning tokens" in requests[-1]["messages"][0]["content"]
    assert requests[-1]["thinking_token_budget"] == 1000
    assert requests[-1]["messages"][:-1] == previous_request["messages"]
    assert "Answer now" in requests[-1]["messages"][-1]["content"]
    assert "PRIVATE_REASONING_MUST_NOT_BE_REPLAYED" not in json.dumps(requests)
    assert latest["messages"][1] == saved_opening
    assert latest["messages"][-1]["recovery_from_call_id"] == recovery["call_id"]
    assert latest["output_recovery"] is None
    with r.store.tx() as c:
        assert digest(r.store.get(c, previous["id"], "call")) == previous_hash
        calls = r.store.list(c, "call", failed["chat"]["mission_id"])
        assert calls[-1]["internal_reasoning_resumed"] is False
        assert r.budget.summary(c)["settled_usd"] > failed["budget"]["settled_usd"]
        assert r.budget.summary(c)["absolute_cap_usd"] == 24


def test_partial_markdown_is_reused_and_joined_without_replaying_completed_openings(
    client, app, monkeypatch
):
    _r, failed, requests = failed_opening(
        client,
        app,
        monkeypatch,
        draft="## Saved approach\nKeep the useful draft.",
        reasoning=11900,
    )
    recovery = failed["output_recovery"]
    assert recovery["answer_tokens"] == 100 and recovery["partial_answer"].startswith(
        "## Saved"
    )
    assert recovery["action_label"] == "Continue saved answer"
    response = recover(client, failed)
    assert response.is_success, response.text
    assert app.state.executor.run_once()
    latest = client.get("/api/chats/" + failed["chat"]["id"]).json()
    assert requests[-1]["messages"][-2] == {
        "role": "assistant",
        "content": recovery["partial_answer"],
    }
    answer = latest["messages"][-1]["content"]
    assert (
        answer
        == recovery["partial_answer"] + "\n\nThe remaining conclusion is complete."
    )
    assert (
        len(requests) == 3
        and latest["accounting"]["replies"][latest["messages"][-1]["id"]]["total"][
            "attempts"
        ]
        == 2
    )


def test_recovery_rejects_wrong_call_or_changed_context_without_spending(
    client, app, monkeypatch
):
    r, failed, requests = failed_opening(client, app, monkeypatch)
    bad = client.post(
        f"/api/chats/{failed['chat']['id']}/control",
        headers={"Idempotency-Key": "wrong-call"},
        json={
            "action": "recover_output",
            "recovery_call_id": "call_unrelated",
        },
    )
    assert bad.status_code == 409
    r.library.ingest(
        failed["chat"], b"A new user-supplied constraint.", title="New source"
    )
    updated = client.get("/api/chats/" + failed["chat"]["id"]).json()
    assert not updated["output_recovery"]["available"]
    assert "changed" in updated["output_recovery"]["reason"]
    assert recover(client, failed).status_code == 409
    assert len(requests) == 2
    with r.store.tx() as c, pytest.raises(DomainError, match="authorization"):
        r.chat.output_recovery.prepare(
            c,
            failed["chat"]["mission_id"],
            "zai-org/GLM-5.3-Flash",
            f"chat:{failed['chat']['id']}:review:1:opening:member_2",
            failed["output_recovery"]["call_id"],
            12000,
        )


def test_missing_reasoning_counter_stays_unknown(client, app, monkeypatch):
    _, failed, _ = failed_opening(client, app, monkeypatch, reasoning=None)
    value = failed["output_recovery"]
    assert value["reasoning_tokens"] is None and value["answer_tokens"] is None
    assert value["output_tokens"] == 12000


def test_structured_stage_recovery_returns_a_complete_schema_not_concatenated_json(
    client, app, monkeypatch
):
    r = setup_testing(app)
    original, requests = httpx.Client, []

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
            if turn["phase"] == "opening":
                demo_turn = deepcopy(turn)
                demo_turn["participant"]["model"] = [
                    "demo/analyst",
                    "demo/critic",
                    "demo/builder",
                ][len(requests) % 3]
                text = r.chat.demo_answer(chat, messages, demo_turn)
            else:
                text = r.chat.review.demo(c, chat, messages, turn)
        truncate = turn["phase"] == "extraction" and len(requests) == 4
        requests.append(body)
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [
                    {
                        "finish_reason": "length" if truncate else "stop",
                        "message": {"content": '{"claims":[' if truncate else text},
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 200,
                    "completion_tokens_details": {"reasoning_tokens": 100},
                },
            },
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    response = client.post(
        "/api/chats",
        headers={"Idempotency-Key": "structured-recovery"},
        json={
            "prompt": "Compare engineering choices and their boundary conditions.",
            "provider": "nebius_token_factory",
            "review_protocol": "reviewed_v3",
            "models": r.settings.models,
            "budget_usd": 1,
        },
    )
    assert response.is_success, response.text
    cid = response.json()["chat"]["id"]
    for _ in range(5):
        assert app.state.executor.run_once()
    failed = client.get("/api/chats/" + cid).json()
    assert failed["output_recovery"]["mode"] == "complete_stage"
    assert failed["output_recovery"]["partial_answer"] == '{"claims":['
    assert recover(client, failed).is_success
    assert app.state.executor.run_once()
    latest = client.get("/api/chats/" + cid).json()
    assert latest["chat"]["status"] == "running", latest["chat"].get("error")
    assert latest["messages"][-1]["phase"] == "extraction"
    assert latest["review"]["claims"]
    assert "ONE COMPLETE response" in requests[-1]["messages"][-1]["content"]
    assert len(requests) == 6


def test_changed_context_after_click_prevents_recovery_dispatch(
    client, app, monkeypatch
):
    r, failed, requests = failed_opening(client, app, monkeypatch)
    assert recover(client, failed).is_success
    r.library.ingest(
        failed["chat"], b"Additional constraint after the click.", title="New input"
    )
    assert app.state.executor.run_once()
    latest = client.get("/api/chats/" + failed["chat"]["id"]).json()
    assert latest["chat"]["status"] == "failed"
    assert "obsolete" in latest["chat"]["error"]
    assert len(requests) == 2


def test_repeated_truncations_reuse_public_drafts_until_physical_window_cannot_fit_review(
    client, app, monkeypatch
):
    original = httpx.Client
    _r, view, requests = failed_opening(
        client, app, monkeypatch, draft="First saved paragraph.", reasoning=11900
    )

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": f"Saved continuation {len(requests)}."},
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 12000,
                    "completion_tokens_details": {"reasoning_tokens": 11900},
                },
            },
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    attempt = 0
    while view["output_recovery"]["available"]:
        assert attempt < 20
        assert view["output_recovery"]["available"]
        assert recover(client, view).is_success
        assert app.state.executor.run_once()
        view = client.get("/api/chats/" + view["chat"]["id"]).json()
        assert view["chat"]["status"] == "failed"
        assert "First saved paragraph." in view["output_recovery"]["partial_answer"]
        assert (
            f"Saved continuation {attempt + 3}."
            in view["output_recovery"]["partial_answer"]
        )
        assert not app.state.executor.run_once()
        attempt += 1
    assert attempt > 3
    assert len(requests) == attempt + 2 <= 20
    assert not view["output_recovery"]["available"]
    assert "attempt limit" in view["output_recovery"]["reason"]
    assert recover(client, view).status_code == 409
    assert len(requests) == attempt + 2


def test_recovery_reuses_source_context_pack_without_repeating_research(
    client, app, monkeypatch
):
    r, view, requests = failed_opening(
        client,
        app,
        monkeypatch,
        draft="Saved public answer.",
        reasoning=11900,
        with_source=True,
    )
    with r.store.tx() as c:
        original_call = r.store.get(c, view["output_recovery"]["call_id"], "call")
        saved_pack = original_call["context_pack_id"]
        saved_tools = r.store.list(c, "tool_invocation", view["chat"]["mission_id"])
        saved_reads = r.store.list(c, "source_read", view["chat"]["mission_id"])
    assert saved_pack and saved_reads
    assert recover(client, view).is_success
    assert app.state.executor.run_once()
    with r.store.tx() as c:
        calls = r.store.list(c, "call", view["chat"]["mission_id"])
        assert calls[-1]["context_pack_id"] == saved_pack
        assert (
            r.store.list(c, "tool_invocation", view["chat"]["mission_id"])
            == saved_tools
        )
        assert r.store.list(c, "source_read", view["chat"]["mission_id"]) == saved_reads
    assert requests[-1]["messages"][:2] == requests[-2]["messages"][:2]


def test_source_removed_after_authorization_blocks_saved_context_replay(
    client, app, monkeypatch
):
    r, view, requests = failed_opening(client, app, monkeypatch, with_source=True)
    assert recover(client, view).is_success
    with r.store.tx() as c:
        source = r.store.list(c, "source", view["chat"]["mission_id"])[0]
        r.library.forget(c, view["chat"], source["id"])
    assert app.state.executor.run_once()
    latest = client.get("/api/chats/" + view["chat"]["id"]).json()
    assert latest["chat"]["status"] == "failed"
    assert not latest["output_recovery"]["available"]
    assert "source was removed" in latest["output_recovery"]["reason"]
    assert len(requests) == 2


def test_join_draft_preserves_repeated_sentence_and_complete_replacement():
    assert (
        join_draft("Start. The unfinished sentence", "The unfinished sentence ends.")
        == "Start. The unfinished sentence ends."
    )
    assert (
        join_draft("A complete draft", "A complete draft with a conclusion")
        == "A complete draft with a conclusion"
    )
