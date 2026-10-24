import json
import time
from types import SimpleNamespace

import httpx
import pytest
from test_budget import configured
from test_token_factory_research import setup_testing

from zerowall.budget import cost_micro
from zerowall.db import DomainError
from zerowall.token_factory_generation import profile


def sse(model, *, complete=True, private=True, text="A complete public answer."):
    chunks = []
    if private:
        chunks.append(
            {
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"reasoning_content": "DO_NOT_STORE_THIS_REASONING"},
                    }
                ],
            }
        )
    chunks.append(
        {"model": model, "choices": [{"index": 0, "delta": {"content": text}}]}
    )
    if complete:
        chunks.extend(
            [
                {
                    "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                },
                {
                    "model": model,
                    "choices": [],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 60,
                        "completion_tokens_details": {"reasoning_tokens": 40},
                    },
                },
            ]
        )
    return (
        "\n\n".join("data: " + json.dumps(chunk) for chunk in chunks)
        + "\n\ndata: [DONE]\n\n"
    )


def test_streamed_raw_opening_retains_large_answer_and_fits_exact_remaining_money(
    client, app, monkeypatch
):
    r = setup_testing(app)
    original, requests, maxima = httpx.Client, [], []
    long_answer = "A useful independent opening with its assumptions. " * 800

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        with r.store.tx() as c:
            call = r.store.list(c, "call", mid)[-1]
            reservation = c.execute(
                "SELECT * FROM reservations WHERE id=?", (call["reservation_id"],)
            ).fetchone()
            bound = json.loads(reservation["body"])
            maxima.append(reservation["maximum_microusd"])
            assert 0 < reservation["maximum_microusd"] <= 100000
            generation = call["generation"]
            assert (
                generation["profile"] == "raw_opening"
                and generation["reasoning"] == "medium"
            )
            assert (
                "remaining_existing_credit_allowance" in generation["limiting_factors"]
            )
            assert (
                cost_micro(
                    generation["input_bound"],
                    bound["output_bound"] + 1,
                    bound["prices"],
                )
                > 100000
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=sse(body["model"], text=long_answer),
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    response = client.post(
        "/api/chats",
        headers={"Idempotency-Key": "raw-opening-study"},
        json={
            "provider": "nebius_token_factory",
            "prompt": "Give the best five engineering options and explain each.",
            "models": r.settings.models,
            "budget_usd": 0.1,
        },
    )
    assert response.is_success, response.text
    cid, mid = response.json()["chat"]["id"], response.json()["chat"]["mission_id"]
    assert app.state.executor.run_once()
    view = client.get("/api/chats/" + cid).json()
    assert view["chat"]["status"] == "running", view["chat"].get("error")
    assert view["messages"][-1]["content"] == long_answer.strip()
    assert len(view["messages"][-1]["content"]) > 16000
    body = requests[0]
    assert (
        body["messages"][1]["content"]
        == "Give the best five engineering options and explain each."
    )
    assert body["stream"] is True and body["stream_options"] == {"include_usage": True}
    assert body["max_completion_tokens"] > 12000
    assert body["chat_template_kwargs"] == {
        "enable_thinking": True,
        "medium_effort": True,
    }
    assert "reasoning_effort" not in body and "response_format" not in body
    assert "at most 4,000 reasoning tokens" in body["messages"][0]["content"]
    assert "240 words" not in json.dumps(
        body
    ) and "two material assertions" not in json.dumps(body)
    assert "concise" not in body["messages"][0]["content"].lower()
    attempt = view["accounting"]["attempts"][-1]
    assert attempt["usage"]["categories"]["output_reasoning"] == 40
    assert attempt["usage"]["categories"]["output_visible"] == 20
    assert (
        attempt["generation"]["effective_output_tokens"]
        == body["max_completion_tokens"]
    )
    with r.store.tx() as c:
        call = r.store.list(c, "call", mid)[0]
        raw = r.artifacts.read(r.store.get(c, call["artifact_id"], "artifact"))
        assert "DO_NOT_STORE_THIS_REASONING" not in json.dumps(raw)
        assert r.budget.summary(c)["absolute_cap_usd"] == 24
    assert len(requests) == 1


@pytest.mark.parametrize(
    "model,reasoning,controls",
    [
        (
            "nvidia/Nemotron-3.5-Super-VL",
            "medium",
            {"chat_template_kwargs": {"enable_thinking": True, "medium_effort": True}},
        ),
        (
            "zai-org/GLM-5.3-Flash",
            "low",
            {
                "thinking_token_budget": 1000,
                "reasoning_effort": "low",
                "chat_template_kwargs": {
                    "reasoning_effort": "low",
                    "clear_thinking": True,
                },
            },
        ),
        (
            "nvidia/Nemotron-3_5-Lightning",
            "enabled",
            {"chat_template_kwargs": {"enable_thinking": True}},
        ),
        (
            "deepseek-ai/DeepSeek-V4-Flash-0731",
            "low",
            {
                "reasoning_effort": "low",
                "chat_template_kwargs": {"reasoning_effort": "low"},
            },
        ),
    ],
)
def test_documented_model_controls_are_recorded_and_transported_exactly(
    app, monkeypatch, model, reasoning, controls
):
    r, mid, _ = configured(app, 1)
    setup_testing(app)
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
    generation = profile(
        r.settings, {"phase": "extraction", "participant": {"model": model}}
    )
    text, call = r.provider.call(
        mid,
        "Return the required review result.",
        32768,
        model=model,
        generation=generation,
    )
    assert text == "A complete public answer."
    assert all(requests[0][key] == value for key, value in controls.items())
    assert call["generation"]["reasoning"] == reasoning
    assert call["generation"]["control_status"] == "requested_not_live_verified"
    assert call["generation"]["effective_output_tokens"] == 32768
    assert call["generation"]["stage_output_target_tokens"] == 3000
    assert "Aim for 3,000 public-output tokens" in requests[0]["messages"][0]["content"]
    assert "262,144 tokens" in requests[0]["messages"][0]["content"]
    assert (
        "reasoning_effort" not in requests[0]
        or requests[0]["reasoning_effort"] != "medium"
    )


def test_incomplete_stream_saves_public_partial_and_retains_unknown_charge_once(
    app, monkeypatch
):
    r, mid, model = configured(app, 0.1)
    original, requests = httpx.Client, []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=sse(model, complete=False, text="Saved public partial."),
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    generation = profile(
        r.settings, {"phase": "opening", "participant": {"model": model}}
    )
    with pytest.raises(DomainError, match="unknown"):
        r.provider.call(
            mid,
            "A raw test question.",
            generation["requested_output_tokens"],
            model=model,
            generation=generation,
        )
    assert len(requests) == 1
    with r.store.tx() as c:
        call = r.store.list(c, "call", mid)[0]
        assert call["state"] == "unknown"
        raw = r.artifacts.read(r.store.get(c, call["artifact_id"], "artifact"))
        assert (
            raw["transport_incomplete"]
            and raw["response"]["choices"][0]["message"]["content"]
            == "Saved public partial."
        )
        assert "DO_NOT_STORE_THIS_REASONING" not in json.dumps(raw)
        assert 0 < r.budget.summary(c)["unknown_usd"] <= 0.1


def test_raw_output_cannot_dispatch_when_even_input_and_one_output_token_do_not_fit(
    app, monkeypatch
):
    r, mid, model = configured(app, 0.000001)
    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: pytest.fail("No network dispatch fits this allowance"),
    )
    generation = profile(
        r.settings, {"phase": "opening", "participant": {"model": model}}
    )
    with pytest.raises(DomainError, match="no output space"):
        r.provider.call(
            mid,
            "A raw test question.",
            generation["requested_output_tokens"],
            model=model,
            generation=generation,
        )
    with r.store.tx() as c:
        assert not r.store.list(c, "call", mid)
        assert r.budget.summary(c)["global_committed_usd"] == 0


def test_cancelled_stream_keeps_its_public_partial_and_maximum_charge(app, monkeypatch):
    r, mid, model = configured(app, 0.1)
    original, stopped, requests = httpx.Client, [False], []

    class ReplyStream(httpx.SyncByteStream):
        def __iter__(self):
            yield (
                "data: "
                + json.dumps(
                    {
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": "Public text before pause."},
                            }
                        ],
                    }
                )
                + "\n\n"
            ).encode()
            stopped[0] = True
            yield b'data: {"choices": []}\n\n'

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, stream=ReplyStream()
        )

    clock = iter(range(1, 100))
    monkeypatch.setattr(
        "zerowall.token_factory_stream.time",
        SimpleNamespace(monotonic=lambda: next(clock), perf_counter=time.perf_counter),
    )
    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    generation = profile(
        r.settings, {"phase": "opening", "participant": {"model": model}}
    )
    with pytest.raises(DomainError, match="unknown"):
        r.provider.call(
            mid,
            "A cancellable raw question.",
            generation["requested_output_tokens"],
            model=model,
            generation=generation,
            cancelled=lambda: stopped[0],
        )
    with r.store.tx() as c:
        call = r.store.list(c, "call", mid)[0]
        raw = r.artifacts.read(r.store.get(c, call["artifact_id"], "artifact"))
        assert call["state"] == "unknown"
        assert (
            raw["response"]["choices"][0]["message"]["content"]
            == "Public text before pause."
        )
        assert r.budget.summary(c)["unknown_usd"] > 0
    assert len(requests) == 1
