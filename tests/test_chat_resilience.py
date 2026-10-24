import httpx
import pytest
from test_council_chat import create, drain, mock_models
from test_workflow import post

from zerowall.db import canonical, now
from zerowall.free_limits import DAILY_ATTEMPTS


def rate_limit(*, daily=False, wait="2", semantic=False):
    return httpx.Response(
        200 if semantic else 429,
        headers={"Retry-After": wait},
        json={
            "error": {
                "code": 429,
                "message": "Rate limit: free-models-per-day"
                if daily
                else "Provider returned error",
                "metadata": {
                    "limit_source": "openrouter_free_models_per_day"
                    if daily
                    else "upstream_provider_shared_pool"
                },
            },
        },
    )


def force_due(app):
    with app.state.research.store.tx() as c:
        c.execute("UPDATE jobs SET body='{}' WHERE state='queued'")
        app.state.research.store.set_setting(c, "openrouter_model_backoff", {})
        app.state.research.store.set_setting(c, "openrouter_free_backoff", None)


def finish(client, app, cid):
    for _ in range(8):
        drain(app)
        view = client.get("/api/chats/" + cid).json()
        if view["chat"]["status"] != "waiting":
            return view
        assert not app.state.executor.run_once(), (
            "A retry dispatched before its due time"
        )
        force_due(app)
    raise AssertionError("Retry policy did not terminate")


def test_temporary_429_recovers_without_replaying_completed_openings(
    client, app, monkeypatch
):
    once = []

    def fail(payload):
        if payload["you"]["name"] == "Xing 4" and not once:
            once.append(True)
            return rate_limit(wait="90")

    seen = mock_models(app, monkeypatch, on_call=fail)
    cid = create(client, "openrouter_free")["chat"]["id"]
    drain(app)
    waiting = client.get("/api/chats/" + cid).json()
    assert waiting["chat"]["status"] == "waiting"
    assert waiting["chat"]["retry_wait"]["attempt"] == 1
    from datetime import UTC, datetime

    assert (
        datetime.fromisoformat(waiting["chat"]["retry_wait"]["not_before"])
        - datetime.now(UTC)
    ).total_seconds() >= 89
    assert len(waiting["messages"]) == 2 and len(seen) == 2
    assert not app.state.executor.run_once()
    app.state.research.store.recover()
    assert client.get("/api/chats/" + cid).json()["chat"]["status"] == "waiting"
    force_due(app)
    result = finish(client, app, cid)
    assert result["chat"]["status"] == "completed" and not result["degraded"]
    assert len(seen) == 11
    assert (
        sum(
            p["you"]["name"] == "Nemotron Super" and p["phase"] == "opening"
            for _, p in seen
        )
        == 1
    )
    replies = [m for m in result["messages"] if m["role"] == "assistant"]
    assert len(replies) == len({m["turn_key"] for m in replies}) == 10


def test_exhausted_member_does_not_strand_two_available_models(
    client, app, monkeypatch
):
    seen = mock_models(
        app,
        monkeypatch,
        on_call=lambda p: rate_limit() if p["you"]["name"] == "Xing 4" else None,
    )
    cid = create(client, "openrouter_free")["chat"]["id"]
    result = finish(client, app, cid)
    assert result["chat"]["status"] == "completed" and result["degraded"]
    assert len(result["active_members"]) == 2 and len(result["baseline"]) == 2
    assert len(result["chat"]["unavailable_members"]) == 1
    assert result["chat"]["retry_used"] == 2 and len(seen) == 10
    replies = [m for m in result["messages"] if m["role"] == "assistant"]
    assert len(replies) == 7 and all(m["name"] != "Xing 4" for m in replies)
    assert len(seen[-1][1]["unavailable_members"]) == 1
    assert len(seen[-1][1]["members"]) == 2
    assert result["budget"]["settled_usd"] == 0


def test_one_available_model_is_never_presented_as_a_completed_council(
    client, app, monkeypatch
):
    seen = mock_models(
        app,
        monkeypatch,
        on_call=lambda p: rate_limit() if p["you"]["name"] == "Xing 4" else None,
    )
    cid = create(
        client,
        "openrouter_free",
        models=[
            "nvidia/nemotron-3-super-120b-a12b:free",
            "xingchen-agi/xing4.0-29b-a4b:free",
        ],
    )["chat"]["id"]
    result = finish(client, app, cid)
    assert (
        result["chat"]["status"] == "unavailable"
        and not result["chat"]["final_message_id"]
    )
    assert len(result["active_members"]) == 1 and len(seen) == 4
    post(client, f"/chats/{cid}/control", {"action": "finish"})
    drain(app)
    result = client.get("/api/chats/" + cid).json()
    assert (
        result["chat"]["status"] == "completed" and result["chat"]["requested_finish"]
    )
    assert result["degraded"] and len(result["active_members"]) == 1
    assert result["messages"][-1]["partial"]


@pytest.mark.parametrize("action", ["pause", "stop"])
def test_wait_can_be_paused_or_stopped_without_extra_dispatch(
    client, app, monkeypatch, action
):
    seen = mock_models(app, monkeypatch, on_call=lambda p: rate_limit())
    cid = create(client, "openrouter_free")["chat"]["id"]
    drain(app)
    post(client, f"/chats/{cid}/control", {"action": action})
    force_due(app)
    assert not app.state.executor.run_once() and len(seen) == 1


def test_director_can_finish_early_during_another_models_retry_wait(
    client, app, monkeypatch
):
    seen = mock_models(
        app,
        monkeypatch,
        on_call=lambda p: rate_limit() if p["you"]["name"] == "Xing 4" else None,
    )
    cid = create(client, "openrouter_free")["chat"]["id"]
    drain(app)
    post(client, f"/chats/{cid}/control", {"action": "finish"})
    drain(app)
    result = client.get("/api/chats/" + cid).json()
    assert result["chat"]["status"] == "completed" and len(seen) == 3
    assert seen[-1][1]["phase"] == "synthesis"


@pytest.mark.parametrize(
    "status,kind", [(401, "credential"), (402, "account"), (403, "access")]
)
def test_account_failures_stop_without_retries_or_paid_fallback(
    client, app, monkeypatch, status, kind
):
    seen = mock_models(
        app,
        monkeypatch,
        on_call=lambda p: httpx.Response(status, json={"error": {"code": status}}),
    )
    cid = create(client, "openrouter_free")["chat"]["id"]
    result = finish(client, app, cid)
    assert result["chat"]["status"] == "unavailable" and len(seen) == 1
    assert result["chat"]["retry_used"] == 0 and not result["degraded"]
    assert not app.state.executor.run_once()


def test_daily_quota_is_not_retried_as_a_provider_outage(client, app, monkeypatch):
    seen = mock_models(app, monkeypatch, on_call=lambda p: rate_limit(daily=True))
    cid = create(client, "openrouter_free")["chat"]["id"]
    result = finish(client, app, cid)
    assert result["chat"]["status"] == "unavailable" and len(seen) == 1
    assert "daily" in result["chat"]["error"] and result["chat"]["retry_used"] == 0


def test_insufficient_quota_blocks_creation_without_spending_an_inference(
    client, app, monkeypatch
):
    seen = mock_models(app, monkeypatch, quota=2)
    response = client.post(
        "/api/chats",
        headers={"Idempotency-Key": "low-quota"},
        json={
            "prompt": "Discuss a bounded question",
            "mode": "discussion",
            "provider": "openrouter_free",
            "models": [
                "nvidia/nemotron-3-super-120b-a12b:free",
                "xingchen-agi/xing4.0-29b-a4b:free",
            ],
            "max_rounds": 2,
        },
    )
    assert response.status_code == 429 and not seen
    assert "2 free requests" in response.json()["detail"]
    assert not client.get("/api/chats/bootstrap").json()["chats"]


@pytest.mark.parametrize("semantic", [False, True])
def test_transient_http_or_semantic_failure_recovers(
    client, app, monkeypatch, semantic
):
    once = []

    def failure(payload):
        if not once:
            once.append(True)
            return (
                rate_limit(semantic=True)
                if semantic
                else httpx.Response(503, json={"error": {"code": 503}})
            )

    seen = mock_models(app, monkeypatch, on_call=failure)
    cid = create(client, "openrouter_free")["chat"]["id"]
    result = finish(client, app, cid)
    assert result["chat"]["status"] == "completed" and len(seen) == 11
    with app.state.research.store.tx() as c:
        assert not app.state.research.store.setting(c, "openrouter_free_locked", False)


def test_nonzero_cost_even_on_http_failure_locks_all_future_free_calls(
    client, app, monkeypatch
):
    seen = mock_models(
        app,
        monkeypatch,
        on_call=lambda p: httpx.Response(
            503, json={"usage": {"cost": 0.01}, "error": {"code": 503}}
        ),
    )
    cid = create(client, "openrouter_free")["chat"]["id"]
    result = finish(client, app, cid)
    assert result["chat"]["status"] == "unavailable" and len(seen) == 1
    assert result["budget"]["settled_usd"] == 0.01 and result["chat"]["retry_used"] == 0
    with app.state.research.store.tx() as c:
        assert app.state.research.store.setting(c, "openrouter_free_locked", False)


def test_earlier_attempts_stay_counted_but_do_not_prevent_legitimate_recovery(
    client, app, monkeypatch
):
    mock_models(app, monkeypatch)
    view = create(client, "openrouter_free")
    cid = view["chat"]["id"]
    app.state.executor.run_once()
    with app.state.research.store.tx() as c:
        for i in range(3):
            c.execute(
                "INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",
                (
                    f"prior-{i}",
                    view["chat"]["mission_id"],
                    f"prior-{i}",
                    0,
                    0,
                    "settled",
                    canonical(
                        {"provider": "openrouter_free", "catalog_checked_at": now()}
                    ),
                ),
            )
        c.execute(
            "UPDATE jobs SET state='cancelled' WHERE target_id=? AND state='queued'",
            (cid,),
        )
        chat = app.state.research.store.get(c, cid, "chat")
        chat["status"] = "failed"
        app.state.research.store.put(c, "chat", chat)
    post(client, f"/chats/{cid}/control", {"action": "resume"})
    drain(app)
    result = client.get("/api/chats/" + cid).json()
    assert (
        result["chat"]["status"] == "completed" and result["budget"]["attempts"] == 13
    )
    assert result["budget"]["attempt_cap"] == 20


def test_waiting_council_does_not_block_other_jobs(client, app, monkeypatch):
    seen = mock_models(app, monkeypatch, on_call=lambda p: rate_limit())
    waiting = create(client, "openrouter_free")["chat"]["id"]
    drain(app)
    other = create(client)["chat"]["id"]
    drain(app)
    assert client.get("/api/chats/" + other).json()["chat"]["status"] == "completed"
    assert client.get("/api/chats/" + waiting).json()["chat"]["status"] == "waiting"
    assert len(seen) == 1


def test_paused_retry_resumes_with_its_original_due_time(client, app, monkeypatch):
    seen = mock_models(app, monkeypatch, on_call=lambda p: rate_limit(wait="90"))
    cid = create(client, "openrouter_free")["chat"]["id"]
    drain(app)
    before = client.get("/api/chats/" + cid).json()["chat"]["retry_wait"]
    post(client, f"/chats/{cid}/control", {"action": "pause"})
    post(client, f"/chats/{cid}/control", {"action": "resume"})
    after = client.get("/api/chats/" + cid).json()["chat"]
    assert after["status"] == "waiting" and after["retry_wait"] == before
    assert not app.state.executor.run_once() and len(seen) == 1


def test_create_idempotency_replay_survives_later_quota_exhaustion(
    client, app, monkeypatch
):
    mock_models(app, monkeypatch)
    body = {
        "prompt": "Discuss a bounded plan",
        "provider": "openrouter_free",
        "models": [
            "nvidia/nemotron-3-super-120b-a12b:free",
            "xingchen-agi/xing4.0-29b-a4b:free",
        ],
    }
    first = post(client, "/chats", body, key="replay-despite-quota")
    with app.state.research.store.tx() as c:
        quota = app.state.research.store.setting(c, "openrouter_account_status")
        quota.update(remaining=0, used=50)
        app.state.research.store.set_setting(c, "openrouter_account_status", quota)
    repeated = post(client, "/chats", body, key="replay-despite-quota")
    assert first["chat"]["id"] == repeated["chat"]["id"]
    assert len(client.get("/api/chats/bootstrap").json()["chats"]) == 1


def test_runtime_connection_failure_is_counted_and_bounded(client, app, monkeypatch):
    once = []

    def failure(payload):
        if not once:
            once.append(True)
            raise httpx.ReadTimeout("simulated connection loss")

    seen = mock_models(app, monkeypatch, on_call=failure)
    cid = create(client, "openrouter_free")["chat"]["id"]
    result = finish(client, app, cid)
    assert result["chat"]["status"] == "completed" and len(seen) == 11
    with app.state.research.store.tx() as c:
        assert (
            app.state.research.store.list(c, "call", result["chat"]["mission_id"])[0][
                "state"
            ]
            == "unknown"
        )


def test_retry_allowance_is_bounded_across_different_turns(client, app, monkeypatch):
    attempted = set()

    def failure(payload):
        key = (payload["you"]["id"], payload["phase"], payload["round"])
        if key not in attempted:
            attempted.add(key)
            return httpx.Response(503, json={"error": {"code": 503}})

    seen = mock_models(app, monkeypatch, on_call=failure)
    cid = create(client, "openrouter_free")["chat"]["id"]
    result = finish(client, app, cid)
    assert (
        result["chat"]["status"] == "unavailable" and result["chat"]["retry_used"] == 3
    )
    assert len(seen) <= 20 and not result["chat"]["final_message_id"]


def test_unavailable_lead_is_not_impersonated_by_the_final_writer(
    client, app, monkeypatch
):
    seen = mock_models(
        app,
        monkeypatch,
        on_call=lambda p: (
            httpx.Response(404, json={"error": {"code": 404}})
            if p["you"]["name"] == "Nemotron Super"
            else None
        ),
    )
    cid = create(client, "openrouter_free")["chat"]["id"]
    result = finish(client, app, cid)
    assert result["chat"]["status"] == "completed" and result["degraded"]
    assert (
        result["messages"][-1]["name"] == "Xing 4" and result["messages"][-1]["partial"]
    )
    assert all(m.get("name") != "Nemotron Super" for m in result["messages"])
    assert seen[-1][1]["you"]["name"] == "Xing 4"


def test_retry_can_use_exactly_the_remaining_local_allowance(client, app, monkeypatch):
    once = []

    def failure(payload):
        if not once:
            once.append(True)
            return httpx.Response(503, json={"error": {"code": 503}})

    seen = mock_models(app, monkeypatch, on_call=failure, quota=8)
    with app.state.research.store.tx() as c:
        for i in range(DAILY_ATTEMPTS - 8):
            c.execute(
                "INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",
                (
                    f"daily-{i}",
                    "prior-work",
                    f"daily-{i}",
                    0,
                    0,
                    "settled",
                    canonical(
                        {"provider": "openrouter_free", "catalog_checked_at": now()}
                    ),
                ),
            )
    cid = create(client, "openrouter_free", rounds=1)["chat"]["id"]
    result = finish(client, app, cid)
    assert result["chat"]["status"] == "completed" and not result["degraded"]
    assert len(seen) == 8 and result["chat"]["retry_used"] == 1
    assert result["account"]["remaining"] == 0
