import json
from copy import deepcopy
from types import SimpleNamespace

import httpx
import pytest
from test_budget import configured
from test_token_factory_generation import sse
from test_token_factory_research import setup_testing
from test_unified_council import create

from zerowall.db import digest
from zerowall.response_timing import summarize
from zerowall.token_factory_generation import profile
from zerowall.token_factory_stream import complete
from zerowall.usage import normalize


def test_request_rates_include_reasoning_and_never_claim_engine_tps():
    call = {
        "latency_ms": 10000,
        "stream_progress": {"first_event_ms": 200, "first_answer_ms": 8000},
    }
    usage = normalize(
        "nebius_token_factory",
        {
            "completion_tokens": 1000,
            "completion_tokens_details": {"reasoning_tokens": 900},
        },
    )
    timing = summarize(call, usage)
    assert timing["elapsed_seconds"] == 10
    assert timing["first_stream_seconds"] == 0.2
    assert timing["first_answer_seconds"] == 8
    assert timing["output_tokens_per_second"] == 100
    assert timing["visible_tokens_per_second"] == 10
    assert timing["rate_basis"] == "reported_output_tokens_per_request_wall_time"


@pytest.mark.parametrize("duration", [None, 0, -1, float("inf"), True])
def test_absent_invalid_or_zero_duration_never_fabricates_tps(duration):
    timing = summarize(
        {"latency_ms": duration}, normalize("groq", {"completion_tokens": 100})
    )
    assert timing["output_tokens_per_second"] is None


def test_interrupted_request_keeps_time_but_unknown_tokens_and_first_answer():
    timing = summarize(
        {"latency_ms": 323886.98, "interruption_reason": "cancelled_by_director"},
        normalize("nebius_token_factory", None),
    )
    assert timing["elapsed_seconds"] == 323.88698
    assert timing["output_tokens_per_second"] is None
    assert timing["visible_tokens_per_second"] is None
    assert timing["first_answer_seconds"] is None
    assert timing["interruption_reason"] == "cancelled_by_director"


def test_stream_records_first_answer_and_reasoning_activity_without_private_text(
    monkeypatch,
):
    clock, published, capture = [0.0], [], {}
    chunks = [
        (2, {"choices": [{"delta": {"role": "assistant"}}]}),
        (
            3,
            {
                "choices": [
                    {"delta": {"reasoning_content": "NEVER_SAVE_PRIVATE_REASONING"}}
                ]
            },
        ),
        (7, {"choices": [{"delta": {"content": "Public "}}]}),
        (8, {"choices": [{"delta": {"content": "answer."}, "finish_reason": "stop"}]}),
        (9, {"choices": [], "usage": {"completion_tokens": 12}}),
    ]

    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            for moment, chunk in chunks:
                clock[0] = moment
                yield ("data: " + json.dumps(chunk) + "\n\n").encode()

    def handler(request):
        clock[0] = 1
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, stream=Stream()
        )

    monkeypatch.setattr(
        "zerowall.token_factory_stream.time",
        SimpleNamespace(perf_counter=lambda: clock[0], monotonic=lambda: clock[0]),
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response = complete(
            client,
            "https://example.invalid/completions",
            {},
            {},
            capture,
            lambda: False,
            progress=published.append,
            started=0,
        )
    stats = capture["stream_progress"]
    assert stats["headers_received_ms"] == 1000
    assert stats["first_event_ms"] == 2000
    assert stats["first_answer_ms"] == 7000
    assert stats["reasoning_chunks"] == 1 and stats["answer_chunks"] == 2
    assert stats["answer_characters"] == len("Public answer.")
    assert stats["events"] == 5 and stats["phase"] == "finished"
    assert any(p["phase"] == "reasoning" for p in published)
    assert response.json()["choices"][0]["message"]["content"] == "Public answer."
    assert "NEVER_SAVE_PRIVATE_REASONING" not in json.dumps([capture, published])


def test_glm_opening_uses_low_effort_without_shortening_answer_envelope(
    app, monkeypatch
):
    r, mid, _ = configured(app, 0.25)
    setup_testing(app)
    model = r.settings.models[1]
    generation = profile(
        r.settings, {"phase": "opening", "participant": {"model": model}}
    )
    original, requests = httpx.Client, []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, text=sse(model)
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    _, call = r.provider.call(
        mid,
        "Give a complete independent answer.",
        generation["requested_output_tokens"],
        model=model,
        generation=generation,
    )
    body = requests[0]
    assert body["reasoning_effort"] == "low"
    assert body["chat_template_kwargs"] == {
        "reasoning_effort": "low",
        "clear_thinking": True,
    }
    assert body["max_completion_tokens"] > 32768 and generation["word_limit"] is None
    assert call["generation"]["profile"] == "raw_opening"
    assert call["generation"]["reasoning"] == "low"
    assert call["generation"]["control_status"] == "requested_not_live_verified"
    assert call["ttft_ms"] is not None
    assert call["stream_progress"]["answer_characters"] > 0
    # The shared reasoning-budget experiment retains a large answer envelope.
    for model, effort in zip(
        r.settings.models, ["medium", "low", "enabled", "low"]
    ):
        opening = profile(
            r.settings, {"phase": "opening", "participant": {"model": model}}
        )
        assert opening["reasoning"] == effort
        assert (
            opening["word_limit"] is None and opening["reasoning_budget_tokens"] == (1000 if model.startswith("zai-org/GLM") else 4000)
        )
    review = profile(
        r.settings,
        {"phase": "scrutiny", "participant": {"model": r.settings.models[1]}},
    )
    assert review["requested_output_tokens"] == 32768
    assert len(requests) == 1


def test_historical_projection_enriches_timing_without_rewriting_records(client, app):
    chat = create(client)["chat"]
    r = app.state.research
    call = {
        "id": "historic_timed",
        "mission_id": chat["mission_id"],
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "state": "completed",
        "purpose": "old",
        "latency_ms": 10000,
        "usage": {
            "completion_tokens": 1000,
            "completion_tokens_details": {"reasoning_tokens": 900},
        },
    }
    with r.store.tx() as c:
        r.store.put(c, "call", call)
        old = deepcopy(r.accounting.attempt(c, call))
        old.pop("timing")
        r.store.put(c, "usage_record", old)
        hashes = {
            row["id"]: digest(json.loads(row["body"]))
            for row in c.execute("SELECT id,body FROM records")
        }
    for _ in range(2):
        view = client.get("/api/chats/" + chat["id"]).json()
        a = next(
            a for a in view["accounting"]["attempts"] if a["call_id"] == call["id"]
        )
        assert a["timing"]["elapsed_seconds"] == 10
        assert a["timing"]["output_tokens_per_second"] == 100
    with r.store.tx() as c:
        assert hashes == {
            row["id"]: digest(json.loads(row["body"]))
            for row in c.execute("SELECT id,body FROM records")
        }


def test_active_request_exposes_only_timing_not_messages_or_private_artifact(
    client, app
):
    chat = create(client)["chat"]
    r = app.state.research
    with r.store.tx() as c:
        r.store.put(
            c,
            "call",
            {
                "id": "in_flight",
                "mission_id": chat["mission_id"],
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "state": "dispatching",
                "purpose": f"chat:{chat['id']}:opening",
                "sent_at": "2026-10-21T20:00:00+00:00",
                "stream_progress": {
                    "phase": "reasoning",
                    "events": 12,
                    "reasoning_chunks": 11,
                },
                "private_test_value": "MUST_NOT_ENTER_ACTIVE_REQUEST",
            },
        )
    view = client.get("/api/chats/" + chat["id"]).json()
    assert view["active_request"]["stream_progress"]["phase"] == "reasoning"
    assert view["active_request"]["call_id"] == "in_flight"
    assert "MUST_NOT_ENTER_ACTIVE_REQUEST" not in json.dumps(view["active_request"])
    assert (
        view["accounting"]["attempts"][-1]["timing"]["output_tokens_per_second"] is None
    )
