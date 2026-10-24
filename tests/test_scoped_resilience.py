"""Exercise the new protocol through actual adapters using deterministic transport doubles."""

import httpx
import pytest
from test_council_chat import drain
from test_review_resilience import force_due, scripted_transport
from test_workflow import post


@pytest.mark.parametrize(
    "phase", ["opening", "extraction", "scrutiny", "repair", "recheck", "synthesis"]
)
@pytest.mark.parametrize(
    "fault", ["429", "timeout", "error_payload", "truncation", "lost_member"]
)
def test_scoped_failure_paths_preserve_attempts_and_openings(
    client, app, monkeypatch, phase, fault
):
    failures = []

    def failure(payload):
        if payload["phase"] != phase or failures:
            return None
        failures.append(True)
        if fault == "429":
            return httpx.Response(
                429, headers={"Retry-After": "2"}, json={"error": {"code": 429}}
            )
        if fault == "timeout":
            raise httpx.ReadTimeout("Synthetic scoped transport timeout")
        if fault == "error_payload":
            return httpx.Response(
                200, json={"error": {"code": 429, "message": "Synthetic shared limit"}}
            )
        if fault == "lost_member":
            return httpx.Response(
                404, json={"error": {"message": "Selected model unavailable"}}
            )
        return httpx.Response(
            200,
            json={
                "model": payload["you"].get("actual_model", payload["you"]["model"]),
                "choices": [
                    {"message": {"content": "{truncated"}, "finish_reason": "length"}
                ],
            },
        )

    r, seen = scripted_transport(app, monkeypatch, failure)
    v = post(
        client,
        "/chats",
        {
            "prompt": "Compare two generic designs with scoped uncertainty.",
            "provider": "direct_council",
            "models": list(r.direct_provider.entries()),
            "mode": "reviewed",
            "review_protocol": "reviewed_v2",
            "max_rounds": 1,
        },
    )
    cid = v["chat"]["id"]
    drain(app)
    v = client.get("/api/chats/" + cid).json()
    if fault in {"429", "error_payload", "timeout"} or (fault == "truncation" and phase == "scrutiny"):
        assert v["chat"]["status"] == "waiting"
        assert not app.state.executor.run_once()
        force_due(r)
        drain(app)
        v = client.get("/api/chats/" + cid).json()
        assert v["chat"]["status"] == "completed", v["chat"].get("error")
        assert v["budget"]["attempts"] == 13
        assert len([m for m in v["messages"] if m["phase"] == "opening"]) == 4
    else:
        assert v["chat"]["status"] in {
            "failed",
            "unavailable",
            "interrupted",
            "completed",
            "running",
        }, v["chat"]["status"]
        # A missing opening/repair may continue under the existing explicit degraded profile.
        assert v["budget"]["attempts"] >= 1
    assert v["budget"]["attempts"] <= 20
    assert all(
        m.get("source") != "fixture" for m in v["messages"] if m["role"] == "assistant"
    )
    assert not v["chat"]["accepted"]
    assert all(
        "openings" not in p and "claims" not in p
        for p in seen
        if p["phase"] == "opening"
    )


def test_explicit_resume_restores_skipped_selected_author_without_resetting_attempts(
    client, app, monkeypatch
):
    r, seen = scripted_transport(app, monkeypatch)
    v = post(
        client,
        "/chats",
        {
            "prompt": "Recover a selected author explicitly within the original budget.",
            "provider": "direct_council",
            "models": list(r.direct_provider.entries()),
            "mode": "reviewed",
            "review_protocol": "reviewed_v2",
            "max_rounds": 1,
        },
    )
    cid = v["chat"]["id"]
    for _ in range(7):
        assert app.state.executor.run_once()
    with r.store.tx() as c:
        chat = r.store.get(c, cid, "chat")
        record = r.chat.review.record(c, chat)
        turn = r.chat.next_turn(chat, r.chat.messages(c, chat), c)
        assert turn["phase"] == "repair"
        chat.update(
            status="unavailable",
            active_turn=None,
            unavailable_members={
                turn["participant"]["id"]: {
                    **turn["participant"],
                    "reason": "Synthetic retained outage",
                }
            },
        )
        record["skipped_keys"] = [turn["key"]]
        record["partial_reasons"] = ["repair unavailable: Synthetic member"]
        r.store.put(c, "chat", chat)
        r.store.put(c, "chat_review", record)
        c.execute(
            "UPDATE jobs SET state='cancelled' WHERE target_id=? AND state='queued'",
            (cid,),
        )
    v = post(client, f"/chats/{cid}/control", {"action": "resume"})
    assert v["budget"]["attempts"] == 7 and v["remaining_planned_calls"] == 5
    assert not v["chat"]["unavailable_members"]
    drain(app)
    v = client.get("/api/chats/" + cid).json()
    assert v["chat"]["status"] == "completed", v["chat"].get("error")
    assert v["budget"]["attempts"] == 12
    assert len([p for p in seen if p["phase"] == "opening"]) == 4
    assert len(v["review"]["recovery_history"]) == 1
    assert all(x["revision"] == 2 for x in v["review"]["claims"])


@pytest.mark.parametrize(
    "phase", ["opening", "extraction", "scrutiny", "repair", "recheck", "synthesis"]
)
def test_process_crash_in_each_scoped_phase_requires_explicit_recovery(
    client, app, monkeypatch, phase
):
    class ProcessCrash(BaseException):
        pass

    crashed = []

    def failure(payload):
        if payload["phase"] == phase and not crashed:
            crashed.append(True)
            raise ProcessCrash()

    r, _seen = scripted_transport(app, monkeypatch, failure)
    v = post(
        client,
        "/chats",
        {
            "prompt": "Retain scoped review state across an interrupted provider request.",
            "provider": "direct_council",
            "models": list(r.direct_provider.entries()),
            "mode": "reviewed",
            "review_protocol": "reviewed_v2",
            "max_rounds": 1,
        },
    )
    cid = v["chat"]["id"]
    with pytest.raises(ProcessCrash):
        for _ in range(20):
            if not app.state.executor.run_once():
                break
    r.store.recover()
    before = client.get("/api/chats/" + cid).json()
    assert before["chat"]["status"] == "interrupted"
    saved_ids = {m["id"] for m in before["messages"]}
    assert not app.state.executor.run_once()
    post(client, f"/chats/{cid}/control", {"action": "resume"})
    drain(app)
    v = client.get("/api/chats/" + cid).json()
    assert v["chat"]["status"] == "completed", v["chat"].get("error")
    assert saved_ids <= {m["id"] for m in v["messages"]}
    assert v["budget"]["attempts"] == 13
    assert len([m for m in v["messages"] if m["phase"] == "opening"]) == 4
    with r.store.tx() as c:
        assert any(
            call["state"] == "unknown"
            for call in r.store.list(c, "call", v["chat"]["mission_id"])
        )
