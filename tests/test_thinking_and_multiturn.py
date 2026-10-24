"""Thinking controls and durable same-chat operation; all inference is synthetic."""

import io
import json
from copy import deepcopy

import httpx
import pytest
from test_council_chat import drain
from test_output_recovery import failed_opening
from test_token_factory_generation import sse
from test_token_factory_research import setup_testing
from test_unified_council import create

from zerowall.contracts import ChatControl
from zerowall.db import DomainError, digest
from zerowall.review_exports import verify_review_pack
from zerowall.thinking_levels import LEVELS
from zerowall.token_factory_generation import configure, profile


def post(client, path, value, key):
    response = client.post(path, json=value, headers={"Idempotency-Key": key})
    assert response.is_success, response.text
    return response.json()


def token_chat(client, app, **options):
    research = setup_testing(app)
    value = post(
        client,
        "/api/chats",
        {
            "prompt": "Compare engineering approaches with explicit conditions.",
            "provider": "nebius_token_factory",
            "models": research.settings.policy["council_default_models"],
            "budget_usd": 5,
            "review_protocol": "reviewed_v3",  # Historical manual-recovery fixtures retain their original protocol.
            **options,
        },
        "thinking-chat",
    )
    return research, value


@pytest.mark.parametrize("level", list(LEVELS))
@pytest.mark.parametrize("index", range(5))
def test_native_controls_are_model_specific_and_answer_length_is_unchanged(
    app, level, index
):
    settings = app.state.research.settings
    model = settings.models[index]
    for phase in ("opening", "repair"):
        generation = profile(
            settings,
            {"phase": phase, "participant": {"model": model}},
            thinking_level=level,
        )
        request = app.state.research.provider.request(
            "A public question.", 32768, model
        )
        configure(request, generation)
        target = 1000 if model.startswith("zai-org/") else LEVELS[level]["reasoning_tokens"]
        assert generation["reasoning_budget_tokens"] == target
        assert generation["thinking_level"] == level
        assert (
            f"{target:,}"
            in request["messages"][0]["content"]
        )
        assert request["max_completion_tokens"] == 32768
        assert generation["requested_output_tokens"] == (
            262144 if phase == "opening" else 32768
        )
        if model.startswith(("zai-org/", "deepseek-ai/")):
            effort = {
                "quick": "low",
                "balanced": "low",
                "deep": "high",
                "maximum": "max",
            }[level]
            if model.startswith("zai-org/"):
                effort = "low"
                assert request["thinking_token_budget"] == 1000
            assert request["reasoning_effort"] == effort
            assert request["chat_template_kwargs"]["reasoning_effort"] == effort
            if model.startswith("zai-org/"):
                assert request["chat_template_kwargs"]["clear_thinking"] is True
        elif model == "reflection/beam":
            assert request["reasoning_effort"] == {"quick": "low", "balanced": "low", "deep": "medium", "maximum": "high"}[level]
            assert "chat_template_kwargs" not in request
            assert "thinking_token_budget" not in request
        else:
            assert request["chat_template_kwargs"]["enable_thinking"] is True
            assert "reasoning_effort" not in request
            if "Lightning" in model:
                assert request["chat_template_kwargs"] == {"enable_thinking": True}


def test_change_is_audited_idempotent_and_does_not_invalidate_saved_public_context(
    client, app
):
    research, value = token_chat(client, app)
    cid = value["chat"]["id"]
    with research.store.tx() as c:
        chat = research.store.get(c, cid, "chat")
        context = research.chat.output_recovery.context_hash(c, chat)
        jobs = [tuple(r) for r in c.execute("SELECT * FROM jobs ORDER BY rowid")]
        money = [
            tuple(r) for r in c.execute("SELECT * FROM reservations ORDER BY rowid")
        ]
    response = post(
        client, f"/api/chats/{cid}/thinking", {"level": "deep"}, "thinking-once"
    )
    assert response["reasoning_budget_tokens"] == 8000
    assert (
        post(client, f"/api/chats/{cid}/thinking", {"level": "deep"}, "thinking-once")
        == response
    )
    assert (
        client.post(
            f"/api/chats/{cid}/thinking",
            json={"level": "off"},
            headers={"Idempotency-Key": "invalid-thinking"},
        ).status_code
        == 422
    )
    with research.store.tx() as c:
        current = research.store.get(c, cid, "chat")
        assert (
            current["protocol"] == chat["protocol"]
            and current["generation"] == chat["generation"]
        )
        assert research.chat.output_recovery.context_hash(c, current) == context
        assert [
            tuple(r) for r in c.execute("SELECT * FROM jobs ORDER BY rowid")
        ] == jobs
        assert [
            tuple(r) for r in c.execute("SELECT * FROM reservations ORDER BY rowid")
        ] == money
        assert not research.store.list(c, "call", chat["mission_id"])


def test_reconfigured_recovery_has_one_consistent_reasoning_target_and_unchanged_public_context(
    app,
):
    research = app.state.research
    turn = {"phase": "opening", "participant": {"model": research.settings.models[3]}}
    request = research.provider.request(
        "Preserve this original public question.", 32768, turn["participant"]["model"]
    )
    configure(request, profile(research.settings, turn, thinking_level="quick"))
    original_public = deepcopy(request["messages"][1:])
    request["messages"].append(
        {"role": "assistant", "content": "A saved partial public answer."}
    )
    recovery = profile(research.settings, turn, recovery=True, thinking_level="deep")
    configure(request, recovery)
    assert request["messages"][1:-1] == original_public
    assert request["messages"][-1]["content"] == "A saved partial public answer."
    assert (
        request["messages"][0]["content"].count("Reasoning budget for this request:")
        == 1
    )
    assert "at most 8,000 reasoning tokens" in request["messages"][0]["content"]
    assert "at most 2,000 reasoning tokens" not in request["messages"][0]["content"]
    assert request["reasoning_effort"] == "low"


def synthetic_council(app, monkeypatch, observations):
    research = app.state.research
    original_client = httpx.Client

    def handler(request):
        body = json.loads(request.content)
        with research.store.tx() as c:
            chat = json.loads(
                c.execute(
                    "SELECT body FROM records WHERE kind='chat' ORDER BY rowid DESC LIMIT 1"
                ).fetchone()[0]
            )
            messages = research.chat.messages(c, chat)
            turn = research.chat.next_turn(chat, messages, c)
            if turn["phase"] == "opening" or chat.get("mode") == "discussion":
                demo_turn = deepcopy(turn)
                demo_turn["participant"]["model"] = [
                    "demo/analyst",
                    "demo/critic",
                    "demo/builder",
                ][int(turn["participant"]["id"].split("_")[-1]) % 3]
                content = research.chat.demo_answer(chat, messages, demo_turn)
                if turn["phase"] == "opening" and chat.get("review_cycle", 1) > 1:
                    assert (
                        "Historical council checkpoint"
                        in body["messages"][1]["content"]
                    )
                    assert "not new evidence" in body["messages"][1]["content"]
            else:
                content = research.chat.review.demo(c, chat, messages, turn)
            call = research.store.list(c, "call", chat["mission_id"])[-1]
            observations.append(
                {
                    "turn_key": turn["key"],
                    "level": call["generation"]["thinking_level"],
                    "budget": call["generation"]["reasoning_budget_tokens"],
                    "model": body["model"],
                    "cycle": chat.get("review_cycle"),
                    "phase": turn["phase"],
                }
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=sse(body["model"], text=content),
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original_client(**kw, transport=httpx.MockTransport(handler)),
    )


def test_eight_full_review_cycles_share_one_chat_and_preserve_history_context_and_credit(
    client, app, monkeypatch
):
    _research, value = token_chat(client, app)
    cid = value["chat"]["id"]
    observations = []
    synthetic_council(app, monkeypatch, observations)
    previous = None
    for cycle in range(1, 9):
        level = list(LEVELS)[(cycle - 1) % 4]
        post(client, f"/api/chats/{cid}/thinking", {"level": level}, f"level-{cycle}")
        if previous:
            post(
                client,
                f"/api/chats/{cid}/messages",
                {
                    "text": f"Revision {cycle}: refine the previous conditional recommendation and address its unresolved concerns."
                },
                f"followup-{cycle}",
            )
        drain(app)
        current = client.get(f"/api/chats/{cid}").json()
        assert current["chat"]["status"] == "completed", current["chat"].get("error")
        assert current["review"]["cycle"] == cycle
        assert current["budget"]["absolute_cap_usd"] == 24
        assert not current["review"].get("synthesis_fallback")
        assert all(
            item["level"] == level
            and item["budget"] == (
                1000 if item["model"].startswith("zai-org/")
                else LEVELS[level]["reasoning_tokens"]
            )
            for item in observations
            if item["cycle"] == cycle
        )
        if previous:
            assert (
                current["messages"][: len(previous["messages"])] == previous["messages"]
            )
            checkpoint = current["review"]["conversation_checkpoint"]
            assert checkpoint["source_cycle"] == cycle - 1 and checkpoint["completed"]
            assert (
                checkpoint["prior_answer"]["text"]
                == previous["messages"][-1]["content"]
            )
            assert (
                checkpoint["prior_assertions"][0]["text"]
                == previous["review"]["claims"][0]["text"]
            )
            assert (
                checkpoint["prior_concerns"][0]["objection"]
                == previous["review"]["findings"][0]["objection"]
            )
            assert current["review"]["conversation_checkpoint_hash"] == digest(
                checkpoint
            )
            assert "conversation_checkpoint" not in checkpoint
        previous = current
    assert len(observations) > 60
    assert len({item["turn_key"] for item in observations}) == len(observations)
    exported = post(
        client, f"/api/chats/{cid}/review/exports", {}, "eight-cycle-export"
    )
    assert verify_review_pack(io.BytesIO(client.get(exported["download"]).content))[
        "reproduced"
    ]


def test_explanations_and_targeted_challenges_continue_repeatedly_without_new_chat(
    client, app
):
    initial = create(client)
    cid = initial["chat"]["id"]
    drain(app)
    for index in range(3):
        before = client.get(f"/api/chats/{cid}").json()
        post(
            client,
            f"/api/chats/{cid}/messages",
            {"text": "Explain the current evidence limits.", "action": "explain"},
            f"explain-{index}",
        )
        drain(app)
        after = client.get(f"/api/chats/{cid}").json()
        assert after["chat"]["status"] == "completed", after["chat"].get("error")
        assert len(after["messages"]) == len(before["messages"]) + 2
        assert "No new checks were performed" in after["messages"][-1]["content"]
        post(
            client,
            f"/api/chats/{cid}/messages",
            {
                "text": "Challenge this assertion within its declared boundary.",
                "action": "challenge",
                "claim_ids": [after["review"]["claims"][0]["claim_id"]],
            },
            f"challenge-{index}",
        )
        drain(app)
        assert client.get(f"/api/chats/{cid}").json()["chat"]["status"] == "completed"


def test_ordinary_token_factory_discussion_can_pass_the_old_six_round_ceiling(
    client, app, monkeypatch
):
    _research, value = token_chat(
        client, app, mode="discussion", review_protocol="reviewed_v1"
    )
    cid = value["chat"]["id"]
    observations = []
    synthetic_council(app, monkeypatch, observations)
    drain(app)
    for index in range(7):
        post(
            client,
            f"/api/chats/{cid}/messages",
            {"text": f"Continue the same discussion, follow-up {index}."},
            f"discussion-{index}",
        )
        drain(app)
        current = client.get(f"/api/chats/{cid}").json()
        assert current["chat"]["status"] == "completed", current["chat"].get("error")
    assert current["chat"]["max_rounds"] == 8
    assert len(observations) > 30


def test_pausing_a_request_that_later_fails_clears_its_active_turn(
    client, app, monkeypatch
):
    research, value = token_chat(client, app)
    cid = value["chat"]["id"]

    def paused_request(*args, **kwargs):
        with research.store.tx() as c:
            assert research.store.get(c, cid, "chat")["active_turn"]["job_id"]
            research.chat.control(c, cid, ChatControl(action="pause"))
        raise DomainError("The paused request ended without another response", 409)

    monkeypatch.setattr(research.provider, "call", paused_request)
    assert app.state.executor.run_once()
    current = client.get(f"/api/chats/{cid}").json()
    assert current["chat"]["status"] == "paused"
    assert current["chat"]["active_turn"] is None
    assert not app.state.executor.run_once()
    assert current["next_turn"]["phase"] == "opening"


def test_restart_of_a_paused_job_does_not_leave_a_stale_active_marker_or_replay(
    client, app
):
    research, value = token_chat(client, app)
    cid = value["chat"]["id"]
    job = app.state.executor.claim()
    with research.store.tx() as c:
        chat = research.store.get(c, cid, "chat")
        chat.update(
            status="paused", active_turn={"job_id": job["id"], "phase": "opening"}
        )
        research.store.put(c, "chat", chat)
    research.store.recover()
    current = client.get(f"/api/chats/{cid}").json()
    assert (
        current["chat"]["status"] == "paused" and current["chat"]["active_turn"] is None
    )
    assert not app.state.executor.run_once()
    with research.store.tx() as c:
        assert not research.store.list(c, "call", value["chat"]["mission_id"])


def test_allowance_amendment_is_explicit_idempotent_and_keeps_the_original_brief_and_ledger(
    client, app
):
    research, value = token_chat(client, app, budget_usd=0.25)
    cid = value["chat"]["id"]
    with research.store.tx() as c:
        mission = research.store.get(c, value["chat"]["mission_id"], "mission")
        jobs = [tuple(r) for r in c.execute("SELECT * FROM jobs ORDER BY rowid")]
        money = [
            tuple(r) for r in c.execute("SELECT * FROM reservations ORDER BY rowid")
        ]
    result = post(
        client, f"/api/chats/{cid}/allowance", {"add_usd": 0.5}, "allowance-once"
    )
    assert result["cap_usd"] == 0.75
    assert (
        post(client, f"/api/chats/{cid}/allowance", {"add_usd": 0.5}, "allowance-once")
        == result
    )
    failed = client.post(
        f"/api/chats/{cid}/allowance",
        json={"add_usd": 24},
        headers={"Idempotency-Key": "over-authority"},
    )
    assert failed.status_code == 402
    with research.store.tx() as c:
        assert (
            research.store.get(c, mission["id"], "mission")["brief"] == mission["brief"]
        )
        assert [
            tuple(r) for r in c.execute("SELECT * FROM jobs ORDER BY rowid")
        ] == jobs
        assert [
            tuple(r) for r in c.execute("SELECT * FROM reservations ORDER BY rowid")
        ] == money
        assert research.budget.summary(c)["absolute_cap_usd"] == 24


def test_discussion_keeps_complete_baseline_history_and_every_director_instruction(
    client, app
):
    research, value = token_chat(
        client, app, mode="discussion", review_protocol="reviewed_v1"
    )
    chat = value["chat"]
    long_text = "An exact scoped public contribution with required qualifiers. " * 350
    with research.store.tx() as c:
        for participant in chat["participants"]:
            research.chat.message(
                c,
                chat,
                role="assistant",
                content=long_text,
                phase="opening",
                model=participant["model"],
                name=participant["name"],
                participant_id=participant["id"],
            )
        for index in range(3):
            research.chat.message(
                c,
                chat,
                role="user",
                content=f"Keep director constraint {index} active.",
                phase="intervention",
            )
            research.chat.message(
                c,
                chat,
                role="assistant",
                content=long_text,
                phase="debate",
                round=index + 1,
                model=chat["participants"][0]["model"],
                name="First member",
            )
        turn = {"phase": "debate", "round": 4, "participant": chat["participants"][0]}
        text, _ = research.chat.prompt(chat, research.chat.messages(c, chat), turn, c)
        body = json.loads(text)
        assert all(item["answer"] == long_text for item in body["shared_baseline"])
        assert len(body["director_notes"]) == 3
        assert len(body["discussion_so_far"]) == 3
        assert all(item["answer"] == long_text for item in body["discussion_so_far"])


def test_used_conversation_allowance_stays_in_chat_and_unknown_charge_survives_credit_addition(
    client, app
):
    research, value = token_chat(client, app, budget_usd=0.25)
    cid, mid = value["chat"]["id"], value["chat"]["mission_id"]
    with research.store.tx() as c:
        c.execute(
            "INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",
            (
                "unknown_old",
                mid,
                "unknown_old_call",
                250000,
                None,
                "unknown",
                json.dumps({"provider": "nebius_token_factory"}),
            ),
        )
        financial = [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY rowid")
        ]
    view = client.get(f"/api/chats/{cid}").json()
    assert not view["continuation"]["allowed"]
    assert "here" in view["continuation"]["reason"]
    assert view["conversation_allowance"]["remaining_usd"] == 0
    post(
        client, f"/api/chats/{cid}/allowance", {"add_usd": 0.5}, "extend-after-unknown"
    )
    view = client.get(f"/api/chats/{cid}").json()
    assert (
        view["continuation"]["allowed"]
        and view["conversation_allowance"]["remaining_usd"] == 0.5
    )
    with research.store.tx() as c:
        assert [
            tuple(row) for row in c.execute("SELECT * FROM reservations ORDER BY rowid")
        ] == financial
        assert research.budget.summary(c)["absolute_cap_usd"] == 24


def test_preference_changes_do_not_break_an_authorized_saved_answer_recovery(
    client, app, monkeypatch
):
    research, failed, requests = failed_opening(
        client, app, monkeypatch, draft="A useful saved partial answer."
    )
    cid = failed["chat"]["id"]
    post(
        client,
        f"/api/chats/{cid}/control",
        {
            "action": "recover_output",
            "recovery_call_id": failed["output_recovery"]["call_id"],
        },
        "queued-recovery",
    )
    with research.store.tx() as c:
        before = research.store.get(c, cid, "chat")
        authorization = deepcopy(before["pending_output_recovery"])
    post(
        client,
        f"/api/chats/{cid}/thinking",
        {"level": "deep"},
        "thinking-after-recovery",
    )
    post(client, f"/api/chats/{cid}/context/compact", {}, "compaction-after-recovery")
    with research.store.tx() as c:
        current = research.store.get(c, cid, "chat")
        assert current["revision"] == before["revision"]
        assert current["pending_output_recovery"] == authorization
    assert app.state.executor.run_once()
    assert len(requests) == 3
    latest = client.get(f"/api/chats/{cid}").json()
    assert latest["chat"]["status"] == "running", latest["chat"].get("error")
    assert (
        latest["messages"][-1]["recovery_from_call_id"]
        == failed["output_recovery"]["call_id"]
    )
    assert (
        requests[-1]["messages"][0]["content"].count(
            "Reasoning budget for this request:"
        )
        == 1
    )
    assert "at most 1,000 reasoning tokens" in requests[-1]["messages"][0]["content"]
    assert requests[-1]["thinking_token_budget"] == 1000
