"""1.05 accounting acceptance: real formulas, missing data and immutable replay."""

from copy import deepcopy
from decimal import Decimal

import pytest
from test_unified_council import create

from zerowall.accounting import Accounting
from zerowall.cache_policy import economics, validate_handle
from zerowall.db import DomainError
from zerowall.pricing import calculate, decimal, price_card
from zerowall.usage import normalize


def groq(raw):
    return calculate(normalize("groq", raw), price_card("groq", "openai/gpt-oss-120b"))


def test_A01_cached_tokens_are_not_billed_twice():
    raw = {
        "prompt_tokens": 12000,
        "completion_tokens": 1000,
        "total_tokens": 13000,
        "prompt_tokens_details": {"cached_tokens": 9000},
    }
    value = groq(raw)
    assert Decimal(value["complete_total_usd"]) == Decimal(".001725")
    assert normalize("groq", raw)["categories"]["input_uncached"] == 3000
    assert normalize("groq", raw)["states"]["cache_write_input"] == "not_applicable"


def test_A01_explicit_zero_and_missing_cache_are_different():
    raw = {"prompt_tokens": 12000, "completion_tokens": 1000}
    assert groq(raw)["status"] == "partial_estimate"
    assert groq(raw)["complete_total_usd"] is None
    assert Decimal(groq(raw)["known_subtotal_usd"]) == Decimal(".0006")
    raw["prompt_tokens_details"] = {"cached_tokens": 0}
    assert Decimal(groq(raw)["complete_total_usd"]) == Decimal(".0024")


def test_A01_gemini_reasoning_is_disjoint_while_groq_reasoning_is_inclusive():
    raw = {
        "promptTokenCount": 10000,
        "cachedContentTokenCount": 0,
        "candidatesTokenCount": 500,
        "thoughtsTokenCount": 200,
        "totalTokenCount": 10700,
    }
    usage = normalize("gemini", raw)
    assert usage["categories"]["billable_output"] == 700
    assert Decimal(
        calculate(usage, price_card("gemini", "gemini-3.5-flash-lite"))[
            "complete_total_usd"
        ]
    ) == Decimal(".00475")
    usage = normalize(
        "groq",
        {
            "completion_tokens": 1000,
            "completion_tokens_details": {"reasoning_tokens": 300},
        },
    )
    assert usage["categories"]["output_visible"] == 700
    assert usage["categories"]["billable_output"] == 1000


@pytest.mark.parametrize(
    "raw",
    [
        {"prompt_tokens": -1},
        {"prompt_tokens": True},
        {"prompt_tokens": 1.5},
        {"prompt_tokens": "1"},
        {"prompt_tokens": float("nan")},
        {"prompt_tokens": float("inf")},
        {"prompt_tokens": 1, "prompt_tokens_details": {"cached_tokens": 2}},
        {"completion_tokens": 1, "completion_tokens_details": {"reasoning_tokens": 2}},
        {"prompt_tokens_details": "bad"},
        {"completion_tokens_details": ["bad"]},
    ],
)
def test_A02_invalid_counts_fail_without_silent_coercion(raw):
    assert normalize("groq", raw)["status"] == "invalid"
    assert groq(raw)["status"] == "invalid"


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", True, None, "not money"])
def test_A02_invalid_money_rejected(value):
    with pytest.raises(ValueError):
        decimal(value)


def test_A03_missing_nvidia_rate_is_unknown_and_reported_zero_is_separate():
    usage = normalize("nvidia_nim", {"prompt_tokens": 100, "completion_tokens": 10})
    cost = calculate(
        usage, price_card("nvidia_nim", "nvidia/nemotron-3-super-120b-a12b"), 0
    )
    assert cost["status"] == "unknown"
    assert cost["provider_reported_amount_usd"] == "0"
    assert cost["complete_total_usd"] is None
    assert not cost["invoice_verified"]


def test_A04_writes_storage_tiers_and_currency_are_separate():
    usage = {
        "categories": {
            "input_uncached": 1000,
            "cache_read_input": 2000,
            "cache_write_input": 500,
            "billable_output": 100,
        },
        "states": {},
    }
    card = {
        "id": "synthetic-only",
        "currency": "USD",
        "rates": dict(zip(usage["categories"], ["1", ".1", "1.25", "2"])),
        "storage_rate_per_million_token_hours": "1",
    }
    cost = calculate(usage, card)
    assert Decimal(cost["complete_total_usd"]) == Decimal(".002025")
    assert Decimal(
        calculate(usage, card, storage_token_hours=1500000)["complete_total_usd"]
    ) == Decimal("1.502025")
    assert calculate(usage, card, currency="EUR")["status"] == "invalid"
    assert calculate(usage, card, modality="image")["status"] == "invalid"
    card["context_brackets"] = [
        {"minimum_input": 500, "rates": {"input_uncached": "2"}}
    ]
    assert calculate(usage, card)["status"] == "partial_estimate"
    assert Decimal(
        calculate(usage, card, input_context=1000)["complete_total_usd"]
    ) == Decimal(".003025")


def test_A05_historical_projection_is_read_only_and_partial(client, app):
    initial = create(client)
    r, chat = app.state.research, initial["chat"]
    with r.store.tx() as c:
        calls = [
            {
                "id": "old_a",
                "mission_id": chat["mission_id"],
                "purpose": "first",
                "state": "completed",
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "usage": {
                    "prompt_tokens": 12000,
                    "completion_tokens": 1000,
                    "prompt_tokens_details": {"cached_tokens": 9000},
                },
            },
            {
                "id": "old_b",
                "mission_id": chat["mission_id"],
                "purpose": "second",
                "state": "unknown",
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
            },
        ]
        for call in calls:
            r.store.put(c, "call", call)
        before = deepcopy(r.store.list(c, "call", chat["mission_id"]))
        result = r.accounting.projection(c, chat)
        assert result["total"]["attempts"] == 2
        assert result["total"]["unknown_outcomes"] == 1
        assert result["total"]["cost_state"] == "partial_estimate"
        assert r.store.list(c, "call", chat["mission_id"]) == before
        assert len(Accounting.total(result["attempts"] * 2)["tokens"]) > 0
        assert Accounting.total(result["attempts"] * 2)["attempts"] == 2


def test_A05_price_cards_are_frozen_and_late_usage_reconciles(client, app):
    chat = create(client)["chat"]
    r = app.state.research
    with r.store.tx() as c:
        call = {
            "id": "late",
            "mission_id": chat["mission_id"],
            "purpose": "turn",
            "state": "unknown",
            "provider": "groq",
            "model": "openai/gpt-oss-20b",
        }
        r.accounting.freeze(c, call)
        card_id = call["price_card_id"]
        r.store.put(c, "call", call)
        r.accounting.settle(c, call)
        call.update(
            state="completed",
            usage={
                "prompt_tokens": 100,
                "prompt_tokens_details": {"cached_tokens": 0},
                "completion_tokens": 10,
            },
        )
        r.store.put(c, "call", call)
        r.accounting.settle(c, call)
        projection = r.accounting.projection(c, chat)
        assert projection["total"]["attempts"] == 1
        assert projection["total"]["unknown_outcomes"] == 0
        assert projection["attempts"][0]["price_card"]["id"] == card_id
        assert len(r.store.list(c, "usage_record", chat["mission_id"])) == 2


def test_A19_cache_economics_never_grants_automatic_spending():
    assert economics()["status"] == "unknown"
    result = economics(
        tokens=10000,
        reuses=10,
        input_rate=1,
        read_rate=0.1,
        creation_cost=0,
        storage_cost=0,
        refresh_cost=0,
    )
    assert result["profitable"] and not result["admit"]
    with pytest.raises(DomainError, match="namespace"):
        validate_handle(
            {"provider": "groq"},
            provider="gemini",
            model="x",
            schema_hash="s",
            tools_hash="t",
            now="2026",
        )


def test_A05_original_calculator_version_remains_frozen_when_reading_existing_assessment(
    client, app
):
    r, chat = app.state.research, create(client)["chat"]
    with r.store.tx() as c:
        call = {
            "id": "old_calculator",
            "mission_id": chat["mission_id"],
            "purpose": "old-turn",
            "state": "completed",
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
            "usage": {"promptTokenCount": 10, "candidatesTokenCount": 5},
        }
        r.store.put(c, "call", call)
        original = r.accounting.attempt(c, call)
        original["cost"] = calculate(
            original["usage"], original["price_card"], algorithm_version="cost/1"
        )
        original.pop("call_snapshot_hash")
        r.store.put(c, "usage_record", original)
        current = r.accounting.projection(c, chat)["attempts"][0]
        assert current["cost"]["version"] == "cost/1"
        assert current["cost"] == original["cost"]
        new_comparison = calculate(current["usage"], current["price_card"])
        assert new_comparison["version"] == "cost/2"
        assert Decimal(new_comparison["known_subtotal_usd"]) > Decimal(
            current["cost"]["known_subtotal_usd"]
        )
        assert (
            r.store.get(c, original["id"], "usage_record")["cost"] == original["cost"]
        )
