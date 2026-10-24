import json

import httpx
import pytest
from test_budget import configured
from test_token_factory_generation import sse
from test_token_factory_research import setup_testing

from zerowall.token_factory_generation import (
    configure,
    observe_reasoning_budget,
    profile,
)
from zerowall.usage import normalize


@pytest.mark.parametrize("model_index", range(4))
@pytest.mark.parametrize(
    "phase,recovery", [("opening", False), ("scrutiny", False), ("opening", True)]
)
def test_four_models_receive_reasoning_budget_without_capping_final_answer(
    app, monkeypatch, model_index, phase, recovery
):
    r, mid, _ = configured(app, 0.25)
    setup_testing(app)
    with r.store.tx() as c:
        mission = r.store.get(c, mid, "mission")
        mission["brief"]["budget_usd"] = 0.25
        r.store.put(c, "mission", mission)
    model = r.settings.models[model_index]
    generation = profile(
        r.settings, {"phase": phase, "participant": {"model": model}}, recovery=recovery
    )
    original, requests = httpx.Client, []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        # The model deliberately exceeds the instruction, but its complete answer
        # must still be saved. The instruction is not a numeric provider guarantee.
        stream = sse(model, text="A complete public answer. " * 800)
        stream = stream.replace(
            '"completion_tokens": 60', '"completion_tokens": 10000'
        ).replace('"reasoning_tokens": 40', '"reasoning_tokens": 4500')
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, text=stream
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    question = (
        "Compare the engineering options, assumptions, and unresolved uncertainty."
    )
    answer, call = r.provider.call(
        mid,
        question,
        generation["requested_output_tokens"],
        model=model,
        generation=generation,
    )
    assert len(requests) == 1
    body = requests[0]
    assert body["messages"][1]["content"] == question
    assert (
        body["messages"][0]["content"].count("Reasoning budget for this request:") == 1
    )
    target = 1000 if model_index == 1 else 4000
    assert f"at most {target:,} reasoning tokens" in body["messages"][0]["content"]
    assert "not the length of the final answer" in body["messages"][0]["content"]
    assert body["max_completion_tokens"] > 10000 and len(answer) > 16000
    assert not any(
        key in body
        for key in ("reasoning_budget", "thinking_budget", "max_thinking_tokens")
    )
    assert call["state"] == "completed" and call["settlement"] == "settled"
    assert call["usage"]["completion_tokens_details"]["reasoning_tokens"] == 4500
    assert call["generation"]["reasoning_budget_tokens"] == target
    assert call["generation"]["client_reasoning_stop_enabled"] is False
    if model_index == 1:
        assert body["thinking_token_budget"] == 1000
        assert body["reasoning_effort"] == "low"
    with r.store.tx() as c:
        attempt = r.accounting.attempt(c, call)
        observation = attempt["reasoning_budget_observation"]
        assert observation == {
            "requested_tokens": target,
            "reported_tokens": 4500,
            "over_requested_tokens": 4500 - target,
            "status": "above_requested_budget",
            "enforcement": "system_instruction_only",
        }
        reservation = c.execute(
            "SELECT * FROM reservations WHERE id=?", (call["reservation_id"],)
        ).fetchone()
        assert (
            0
            < reservation["actual_microusd"]
            <= reservation["maximum_microusd"]
            <= 250000
        )
        assert r.budget.summary(c)["absolute_cap_usd"] == 24


def test_instruction_is_idempotent_and_keeps_existing_system_rules(app):
    r = app.state.research
    generation = profile(
        r.settings, {"phase": "opening", "participant": {"model": r.settings.models[0]}}
    )
    request = {
        "messages": [
            {"role": "system", "content": "Use the required review schema."},
            {"role": "user", "content": "An unchanged question."},
        ],
        "max_completion_tokens": 50000,
    }
    configure(request, generation)
    configure(request, generation)
    assert request["messages"][0]["content"].startswith(
        "Use the required review schema."
    )
    assert (
        request["messages"][0]["content"].count(
            generation["reasoning_budget_instruction"]
        )
        == 1
    )
    assert request["messages"][1]["content"] == "An unchanged question."
    assert request["max_completion_tokens"] == 50000


@pytest.mark.parametrize(
    "reported,status",
    [
        (0, "within_requested_budget"),
        (3999, "within_requested_budget"),
        (4000, "within_requested_budget"),
        (4001, "above_requested_budget"),
        (None, "not_reported"),
        (-1, "not_reported"),
    ],
)
def test_budget_observations_are_measured_and_missing_usage_stays_unknown(
    reported, status
):
    usage = normalize(
        "nebius_token_factory",
        {
            "completion_tokens": 6000,
            "completion_tokens_details": {"reasoning_tokens": reported},
        },
    )
    result = observe_reasoning_budget(
        {
            "reasoning_budget_tokens": 4000,
            "reasoning_budget_enforcement": "system_instruction_only",
        },
        usage,
    )
    assert result["status"] == status
    if status == "not_reported":
        assert (
            result["reported_tokens"] is None
            and result["over_requested_tokens"] is None
        )


def test_historical_requests_do_not_receive_retroactive_budget_labels():
    usage = normalize(
        "nebius_token_factory",
        {
            "completion_tokens": 29736,
            "completion_tokens_details": {"reasoning_tokens": 26528},
        },
    )
    assert (
        observe_reasoning_budget({"version": "token-factory-generation/3"}, usage)
        is None
    )
    assert observe_reasoning_budget(None, usage) is None
