import json

import httpx
import pytest

from zerowall.council_chat import DEMO_MODELS
from zerowall.free_provider import CHAT_MODELS
from test_workflow import post


def create(client, provider="fixture", models=None, rounds=2):
    return post(
        client,
        "/chats",
        {
            "prompt": "How should we validate a council's answers?",
            "provider": provider,
            "models": list(
                models or (DEMO_MODELS if provider == "fixture" else CHAT_MODELS[:3])
            ),
            "max_rounds": rounds,
            "mode": "discussion",
        },
    )


def drain(app, maximum=40):
    for _ in range(maximum):
        if not app.state.executor.run_once():
            return
    raise AssertionError("Council did not stop within its bounded schedule")


def mock_models(
    app, monkeypatch, *, ready=False, on_call=None, truncate_first=False, quota=50
):
    app.state.research.settings.openrouter_api_key = "chat-unit-key"
    seen = []
    real = httpx.Client

    def handle(request):
        assert request.url.host == "openrouter.ai"
        if request.method == "GET":
            if request.url.path.endswith("/key"):
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "free_model_daily_requests": {
                                "used": 50 - quota,
                                "limit": 50,
                                "remaining": quota,
                            }
                        }
                    },
                )
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": model, "pricing": {"prompt": "0", "completion": "0"}}
                        for model in CHAT_MODELS
                    ]
                },
            )
        body = json.loads(request.content)
        assert "response_format" not in body
        assert body["provider"]["max_price"] == {
            "prompt": 0,
            "completion": 0,
            "request": 0,
        }
        assert body["provider"]["allow_fallbacks"] is False
        payload = json.loads(body["messages"][-1]["content"])
        assert body["max_tokens"] == (4096 if payload["phase"] == "synthesis" else 3072)
        assert payload["response_budget"]["maximum_output_tokens"] == body["max_tokens"]
        seen.append((body["model"], payload))
        if on_call:
            override = on_call(payload)
            if isinstance(override, httpx.Response):
                return override
        content = f"## {payload['you']['name']} — {payload['phase']}\n\nA public answer to the question."
        if ready and payload["phase"] == "debate":
            content += "\n[[COUNCIL_READY]]"
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "usage": {"prompt_tokens": 100, "completion_tokens": 90, "cost": 0},
                "choices": [
                    {
                        "finish_reason": "length"
                        if truncate_first and len(seen) == 1
                        else "stop",
                        "message": {"content": content},
                    }
                ],
            },
        )

    monkeypatch.setattr(
        "zerowall.free_provider.httpx.Client",
        lambda **kwargs: real(**kwargs, transport=httpx.MockTransport(handle)),
    )
    monkeypatch.setattr("zerowall.free_provider.time.sleep", lambda seconds: None)
    return seen


def test_visible_demo_conversation_runs_openings_two_debates_and_synthesis(client, app):
    initial = create(client)
    cid = initial["chat"]["id"]
    assert len(initial["messages"]) == 1
    drain(app)
    result = client.get("/api/chats/" + cid).json()
    assert result["chat"]["status"] == "completed"
    assert len(result["baseline"]) == 3
    assert len([m for m in result["messages"] if m.get("phase") == "debate"]) == 6
    assert len([m for m in result["messages"] if m.get("phase") == "synthesis"]) == 1
    assert all(
        m["source"] == "fixture" for m in result["messages"] if m["role"] == "assistant"
    )
    assert result["budget"]["attempts"] == 0
    assert result["remaining_planned_calls"] == 0
    assert result["chat"]["mission_id"] not in [
        m["id"] for m in client.get("/api/bootstrap").json()["missions"]
    ]


def test_real_adapter_models_are_distinct_and_debate_sees_previous_turns(
    client, app, monkeypatch
):
    seen = mock_models(app, monkeypatch)
    initial = create(client, "openrouter_free")
    cid = initial["chat"]["id"]
    drain(app)
    result = client.get("/api/chats/" + cid).json()
    assert result["chat"]["status"] == "completed"
    assert len(seen) == 10
    assert len({model for model, _ in seen[:3]}) == 3
    assert all(
        "shared_baseline" not in payload and "discussion_so_far" not in payload
        for _, payload in seen[:3]
    )
    assert len(seen[3][1]["shared_baseline"]) == 3
    assert seen[3][1]["discussion_so_far"] == []
    assert len(seen[4][1]["discussion_so_far"]) == 1
    assert seen[-1][1]["phase"] == "synthesis"
    assert len(seen[-1][1]["discussion_so_far"]) > 0
    assert result["budget"]["attempts"] == 10 and result["budget"]["settled_usd"] == 0
    assert client.get("/api/bootstrap").json()["budget"]["attempts"] == 0


def test_director_note_does_not_contaminate_independent_openings(
    client, app, monkeypatch
):
    seen = mock_models(app, monkeypatch)
    cid = create(client, "openrouter_free")["chat"]["id"]
    app.state.executor.run_once()
    post(
        client,
        f"/chats/{cid}/messages",
        {"text": "Focus on a fair reference baseline."},
    )
    drain(app)
    assert "director_notes" not in seen[1][1] and "director_notes" not in seen[2][1]
    assert (
        seen[3][1]["director_notes"][0]["text"] == "Focus on a fair reference baseline."
    )


def test_pause_during_a_call_preserves_the_answer_without_starting_another(
    client, app, monkeypatch
):
    cid_holder = []

    def during_call(payload):
        if len(cid_holder) == 1:
            post(client, f"/chats/{cid_holder[0]}/control", {"action": "pause"})
            cid_holder.append("paused")

    seen = mock_models(app, monkeypatch, on_call=during_call)
    cid = create(client, "openrouter_free")["chat"]["id"]
    cid_holder.append(cid)
    app.state.executor.run_once()
    assert not app.state.executor.run_once()
    paused = client.get("/api/chats/" + cid).json()
    assert paused["chat"]["status"] == "paused" and len(paused["messages"]) == 2
    post(client, f"/chats/{cid}/control", {"action": "resume"})
    drain(app)
    assert len(seen) == 10
    assert client.get("/api/chats/" + cid).json()["chat"]["status"] == "completed"


def test_truncated_reply_stops_once_and_explicit_resume_preserves_the_failed_attempt(
    client, app, monkeypatch
):
    seen = mock_models(app, monkeypatch, truncate_first=True)
    cid = create(client, "openrouter_free")["chat"]["id"]
    drain(app)
    failed = client.get("/api/chats/" + cid).json()
    assert failed["chat"]["status"] == "failed"
    assert "output token limit" in failed["chat"]["error"]
    assert len(seen) == 1 and len(failed["messages"]) == 1
    assert failed["budget"]["attempts"] == 1
    post(client, f"/chats/{cid}/control", {"action": "resume"})
    drain(app)
    result = client.get("/api/chats/" + cid).json()
    assert result["chat"]["status"] == "completed"
    assert len(seen) == 11 and result["budget"]["attempts"] == 11
    replies = [m for m in result["messages"] if m["role"] == "assistant"]
    assert len(replies) == len({m["turn_key"] for m in replies}) == 10
    with app.state.research.store.tx() as c:
        calls = app.state.research.store.list(c, "call", result["chat"]["mission_id"])
        artifact = app.state.research.store.get(c, calls[0]["artifact_id"], "artifact")
        raw = app.state.research.artifacts.read(artifact)
        assert raw["response"]["choices"][0]["finish_reason"] == "length"


def test_explicit_followup_and_free_call_cap_preserve_existing_final(
    client, app, monkeypatch
):
    seen = mock_models(app, monkeypatch)
    cid = create(client, "openrouter_free", rounds=1)["chat"]["id"]
    drain(app)
    first = client.get("/api/chats/" + cid).json()["chat"]["final_message_id"]
    post(
        client,
        f"/chats/{cid}/messages",
        {"text": "Compare the failure modes more carefully."},
    )
    drain(app)
    result = client.get("/api/chats/" + cid).json()
    assert len(seen) == 11
    assert first != result["chat"]["final_message_id"]
    assert len([m for m in result["messages"] if m.get("phase") == "synthesis"]) == 2
    for _ in range(2):
        post(client, f"/chats/{cid}/messages", {"text": "One more bounded round."})
        drain(app)
    result = client.get("/api/chats/" + cid).json()
    assert result["budget"]["attempts"] == 19
    assert len([m for m in result["messages"] if m.get("phase") == "synthesis"]) == 4
    post(client, f"/chats/{cid}/messages", {"text": "Another full round, please."}, 429)
    assert (
        client.get("/api/chats/" + cid).json()["chat"]["final_message_id"]
        == result["chat"]["final_message_id"]
    )


def test_model_readiness_does_not_skip_the_directors_selected_rounds(
    client, app, monkeypatch
):
    seen = mock_models(app, monkeypatch, ready=True)
    cid = create(client, "openrouter_free")["chat"]["id"]
    drain(app)
    result = client.get("/api/chats/" + cid).json()
    assert len(seen) == 10
    assert (
        len(
            [
                m
                for m in result["messages"]
                if m.get("phase") == "debate" and m["round"] == 2
            ]
        )
        == 3
    )
    assert all("[[COUNCIL_READY]]" not in m["content"] for m in result["messages"])


def test_stop_and_partial_finish_are_explicit_human_controls(client, app):
    cid = create(client)["chat"]["id"]
    app.state.executor.run_once()
    post(client, f"/chats/{cid}/control", {"action": "finish"})
    drain(app)
    result = client.get("/api/chats/" + cid).json()
    assert result["chat"]["status"] == "completed"
    assert len([m for m in result["messages"] if m["role"] == "assistant"]) == 2
    post(client, f"/chats/{cid}/control", {"action": "accept"})
    assert client.get("/api/chats/" + cid).json()["chat"]["accepted"]
    another = create(client)["chat"]["id"]
    post(client, f"/chats/{another}/control", {"action": "stop"})
    assert not app.state.executor.run_once()
    assert client.get("/api/chats/" + another).json()["chat"]["status"] == "cancelled"


def test_restart_requires_explicit_continuation_and_does_not_replay_completed_turns(
    client, app
):
    cid = create(client)["chat"]["id"]
    app.state.executor.run_once()
    assert app.state.executor.claim()
    app.state.research.store.recover()
    assert client.get("/api/chats/" + cid).json()["chat"]["status"] == "interrupted"
    assert not app.state.executor.run_once()
    post(client, f"/chats/{cid}/control", {"action": "resume"})
    drain(app)
    result = client.get("/api/chats/" + cid).json()
    assert len([m for m in result["messages"] if m.get("phase") == "opening"]) == 3


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"models": [CHAT_MODELS[0], CHAT_MODELS[0]]}, 422),
        ({"models": [CHAT_MODELS[0], "a/paid-model"]}, 422),
        ({"max_rounds": 4}, 422),
        ({"budget_usd": 1}, 422),
        (
            {
                "provider": "nebius_token_factory",
                "models": ["nvidia/Nemotron-3.5-Super-VL", "zai-org/GLM-5.3-Flash"],
                "budget_usd": 1,
            },
            412,
        ),
    ],
)
def test_provider_and_conversation_bounds_fail_before_dispatch(
    client, app, monkeypatch, changes, status
):
    seen = mock_models(app, monkeypatch)
    post(
        client,
        "/chats",
        {
            "prompt": "Consider a real question",
            "mode": "discussion",
            "provider": "openrouter_free",
            "models": list(CHAT_MODELS[:3]),
            "max_rounds": 2,
            **changes,
        },
        status,
    )
    assert seen == []


def test_conversation_configuration_is_frozen_and_creation_is_idempotent(client, app):
    body = {
        "prompt": "Discuss a testable plan",
        "provider": "fixture",
        "models": list(DEMO_MODELS),
    }
    a = post(client, "/chats", body, key="one-chat")
    b = post(client, "/chats", body, key="one-chat")
    assert a["chat"]["id"] == b["chat"]["id"]
    with app.state.research.store.tx() as c:
        chat = app.state.research.store.get(c, a["chat"]["id"], "chat")
        chat["participants"][0]["model"] = "different/model"
        app.state.research.store.put(c, "chat", chat)
    app.state.executor.run_once()
    result = client.get("/api/chats/" + a["chat"]["id"]).json()
    assert result["chat"]["status"] == "failed" and "Frozen" in result["chat"]["error"]
    assert len(result["messages"]) == 1
