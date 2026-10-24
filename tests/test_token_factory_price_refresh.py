"""A stale tariff cache never replaces the council or expands payment authority."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from test_token_factory_research import setup_testing

from zerowall.db import DomainError
from zerowall.token_factory_prices import PRICE_CACHE_DAYS, refresh_prices


def expire(research):
    with research.store.tx() as c:
        verification = research.store.setting(c, "live_verification")
        verification["expires_at"] = (
            datetime.now(UTC) - timedelta(seconds=1)
        ).isoformat()
        research.store.set_setting(c, "live_verification", verification)
        return verification


def transport(monkeypatch, *, fail=False):
    calls = []
    catalogue = json.loads(
        Path("docs/validation/reflection-beam-catalog.json").read_text()
    )
    original = httpx.Client

    def handle(request):
        calls.append((request.method, request.url.path))
        assert request.method == "GET"
        if fail:
            raise httpx.ConnectError("Offline catalogue", request=request)
        if request.url.path == "/api/public/models_info":
            return httpx.Response(
                200, json=[{"flavors": [row]} for row in catalogue["selected"]]
            )
        assert request.url.path == "/v1/models"
        return httpx.Response(
            200,
            json={"data": [{"id": row["model_id"]} for row in catalogue["selected"]]},
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kw: original(transport=httpx.MockTransport(handle), **kw),
    )
    return calls


def test_new_price_cache_lasts_seven_days(app):
    r = setup_testing(app, include_beam=True)
    with r.store.tx() as c:
        v = r.store.setting(c, "live_verification")
    remaining = datetime.fromisoformat(v["expires_at"]) - datetime.now(UTC)
    assert timedelta(days=6, hours=23) < remaining <= timedelta(days=7)
    assert v["price_cache_days"] == PRICE_CACHE_DAYS == 7


def test_expired_prices_refresh_with_two_gets_preserving_authority_and_money(
    app, monkeypatch
):
    r = setup_testing(app, include_beam=True)
    before = expire(r)
    with r.store.tx() as c:
        authority = r.store.setting(c, "token_factory_spending_authority")
        reservations = [
            tuple(row) for row in c.execute("select * from reservations order by id")
        ]
    calls = transport(monkeypatch)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _: refresh_prices(r), range(3)))
    assert len(calls) == 2
    with r.store.tx() as c:
        assert r.store.setting(c, "token_factory_spending_authority") == authority
        assert [
            tuple(row) for row in c.execute("select * from reservations order by id")
        ] == reservations
        assert not r.store.list(c, "call", "spending-policy")
        v = r.budget.verification(c, "reflection/beam")
        assert v["authority_id"] == before["authority_id"]
        assert v["operational_cap_usd"] == 24 and v["existing_credit_usd"] == 25
        assert (
            v["price_cache_days"] == 7
            and v["account_payment_settings_verified"] is False
        )
        assert (
            timedelta(days=6, hours=23)
            < datetime.fromisoformat(v["expires_at"]) - datetime.now(UTC)
            <= timedelta(days=7)
        )
        assert r.chat.bootstrap(c)["providers"]["nebius_token_factory"][
            "default_models"
        ] == [
            "nvidia/Nemotron-3.5-Super-VL",
            "reflection/beam",
            "deepseek-ai/DeepSeek-V4-Flash-0731",
        ]
    refresh_prices(r)
    assert len(calls) == 2  # A fresh cache has no network traffic.


def test_failed_refresh_keeps_lineup_and_blocks_only_unpriced_inference(
    client, app, monkeypatch
):
    r = setup_testing(app, include_beam=True)
    r.settings.tavily_api_key = "offline-configured-search"
    before = expire(r)
    calls = transport(monkeypatch, fail=True)
    response = client.get("/api/chats/bootstrap")
    assert response.is_success
    assert response.json()["research"]["default_enabled"] is True
    tf = response.json()["providers"]["nebius_token_factory"]
    assert tf["preferred"] is True and tf["ready"] is False
    assert tf["price_cache_days"] == 7 and len(tf["default_models"]) == 3
    assert tf["default_models"][1] == "reflection/beam"
    assert tf["generation"]["context_tokens"] == 262144
    assert tf["thinking_profiles"]["balanced"]["reasoning_budget_tokens"] == 4000
    assert tf["price_refresh"]["state"] == "unavailable"
    client.get("/api/chats/bootstrap")
    assert len(calls) == 1  # Failure backoff avoids repeated connection attempts.
    with r.store.tx() as c:
        assert r.store.setting(c, "live_verification") == before
        with pytest.raises(DomainError):
            r.budget.verification(c, "reflection/beam")


def test_refresh_cannot_clear_a_bound_breach_or_reauthorize_funding(app, monkeypatch):
    r = setup_testing(app, include_beam=True)
    expire(r)
    with r.store.tx() as c:
        v = r.store.setting(c, "live_verification")
        v["all_billing_categories_bounded"] = False
        r.store.set_setting(c, "live_verification", v)
    calls = transport(monkeypatch)
    refresh_prices(r, force=True)
    assert not calls
    with r.store.tx() as c:
        assert r.store.setting(c, "live_verification") == v
        with pytest.raises(DomainError):
            r.budget.verification(c, "reflection/beam")
