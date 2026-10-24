"""262K context admission must not reuse the inflated financial token bound."""

import json

import httpx
import pytest
from test_budget import configured
from test_token_factory_generation import sse
from test_token_factory_research import setup_testing

from zerowall.context_window import CONTEXT_TOKENS, fit, measure
from zerowall.db import DomainError
from zerowall.research_execution import transport_tools
from zerowall.token_factory_generation import configure, profile


@pytest.mark.parametrize("index", range(4))
def test_every_selected_model_has_a_262k_window_not_a_byte_limit(app, index):
    settings = app.state.research.settings
    model = settings.models[index]
    generation = profile(
        settings, {"phase": "opening", "participant": {"model": model}}
    )
    assert generation["context_tokens"] == CONTEXT_TOKENS == 262144
    assert generation["model_context_tokens"] >= CONTEXT_TOKENS
    assert generation["requested_output_tokens"] == CONTEXT_TOKENS
    assert generation["reasoning_budget_tokens"] == 4000


def test_exact_shared_window_boundary_keeps_output_space_and_never_clips_input():
    request = {
        "max_completion_tokens": 32768,
        "messages": [{"content": "Keep every objection."}],
    }
    original = json.dumps(request)
    assert (
        fit(
            request,
            {
                "context_tokens": CONTEXT_TOKENS,
                "input_context_tokens": CONTEXT_TOKENS - 8192,
            },
        )
        == 8192
    )
    assert (
        fit(
            request,
            {
                "context_tokens": CONTEXT_TOKENS,
                "input_context_tokens": CONTEXT_TOKENS - 1,
            },
        )
        == 1
    )
    with pytest.raises(DomainError, match="262,144-token context window"):
        fit(
            request,
            {"context_tokens": CONTEXT_TOKENS, "input_context_tokens": CONTEXT_TOKENS},
        )
    assert json.dumps(request) == original


def test_large_request_uses_tokens_for_context_but_full_bytes_for_credit(
    app, monkeypatch
):
    research, mid, model = configured(app, 5)
    setup_testing(app)
    original, physical = httpx.Client, []
    text = "Engineering tradeoffs need evidence. " * 40000
    generation = profile(
        research.settings, {"phase": "extraction", "participant": {"model": model}}
    )

    def handler(request):
        body = json.loads(request.content)
        physical.append(body)
        assert len(request.content) > 1000000
        assert body["messages"][-1]["content"] == text
        with research.store.tx() as c:
            call = research.store.list(c, "call", mid)[-1]
            context = call["context_window"]
            assert 230000 < context["input_context_tokens"] < CONTEXT_TOKENS
            assert (
                context["input_context_tokens"] + body["max_completion_tokens"]
                == CONTEXT_TOKENS
            )
            assert 0 < body["max_completion_tokens"] < 32768
            assert call["generation"]["limiting_factors"] == ["council_context"]
            bound = json.loads(
                c.execute(
                    "SELECT body FROM reservations WHERE id=?",
                    (call["reservation_id"],),
                ).fetchone()[0]
            )
            assert bound["input_bound"] > CONTEXT_TOKENS * 5
            assert bound["prices"]["input"] > 0
            assert research.budget.summary(c)["absolute_cap_usd"] == 24
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, text=sse(model)
        )

    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: original(**kw, transport=httpx.MockTransport(handler)),
    )
    answer, call = research.provider.call(
        mid, text, 32768, model=model, generation=generation
    )
    assert answer == "A complete public answer." and len(physical) == 1
    assert (
        call["generation"]["input_context_tokens"] < call["generation"]["input_bound"]
    )


def test_oversized_actual_tokens_stop_before_dispatch_or_reservation(app, monkeypatch):
    research, mid, model = configured(app, 5)
    setup_testing(app)
    monkeypatch.setattr(
        "zerowall.provider.httpx.Client",
        lambda **kw: pytest.fail("Oversized context dispatched"),
    )
    with research.store.tx() as c:
        before = research.budget.summary(c)
    with pytest.raises(
        DomainError, match="No required source, warning or objection was dropped"
    ):
        research.provider.call(mid, "engineering " * 270000, 32768, model=model)
    with research.store.tx() as c:
        assert not research.store.list(c, "call", mid)
        assert research.budget.summary(c) == before


def test_complete_request_count_includes_sources_tools_history_and_reasoning_guide(app):
    research = app.state.research
    model = research.settings.models[0]
    request = research.provider.request(
        "Keep the required review claims.", 32768, model
    )
    basic = measure(request, research.settings)
    options = {
        "mode": "native",
        "prefix": "Saved source with exact qualifiers. " * 5000,
        "catalogue": [{"name": "library_read", "parameters": {"type": "object"}}],
        "history": [
            {
                "role": "tool",
                "tool_call_id": "saved-tool",
                "content": "Required finding and source result. " * 2000,
            }
        ],
    }
    wire = transport_tools({"provider": "nebius_token_factory"}, request, options)
    configure(
        wire,
        profile(
            research.settings, {"phase": "recheck", "participant": {"model": model}}
        ),
    )
    complete = measure(wire, research.settings)
    assert len(json.dumps(wire).encode()) > 120000
    assert len(json.dumps(options["history"]).encode()) > 48000
    assert complete["input_content_tokens"] > basic["input_content_tokens"] + 30000
    assert complete["framing_allowance_tokens"] > basic["framing_allowance_tokens"]
    assert complete["provider_measured"] is False
