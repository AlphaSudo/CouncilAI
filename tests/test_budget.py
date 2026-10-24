from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from zerowall.contracts import MissionBrief
from zerowall.db import DomainError
from zerowall.fixtures import demo_brief


def configured(app, cap=0.001):
    r = app.state.research
    s = r.store
    model = r.settings.models[0]
    with s.tx() as c:
        brief = demo_brief()
        brief["budget_usd"] = 1
        m = r.create_mission(c, MissionBrief.model_validate(brief))
        s.set_setting(
            c,
            "live_verification",
            {
                "id": "test",
                "existing_credit_usd": 25,
                "operational_cap_usd": cap,
                "credit_only_confirmed": True,
                "automatic_payments_disabled": True,
                "token_bound_verified": True,
                "all_billing_categories_bounded": True,
                "catalog_model_ids": [model],
                "prices": {model: {"input": 1, "output": 1}},
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "billed_input_multiplier": 1,
                "additional_billed_output_tokens": 0,
            },
        )
    return r, m["id"], model


def test_concurrent_reservation_cannot_oversubscribe(app):
    r, mid, model = configured(app)

    def reserve(i):
        try:
            with r.store.tx() as c:
                r.budget.reserve(c, mid, model, 300, 300, str(i))
            return True
        except DomainError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(reserve, range(8)))
    assert sum(results) == 1
    with r.store.tx() as c:
        assert r.budget.summary(c)["global_committed_usd"] == 0.0006


def test_unknown_charge_survives_recovery_and_prevents_respend(app):
    r, mid, model = configured(app)
    with r.store.tx() as c:
        r.budget.reserve(c, mid, model, 300, 300, "attempt-1")
    r.store.recover()
    with r.store.tx() as c:
        assert r.budget.summary(c)["unknown_usd"] == 0.0006
        with pytest.raises(DomainError):
            r.budget.reserve(c, mid, model, 300, 300, "attempt-2")


def test_settlement_and_missing_usage(app):
    r, mid, model = configured(app, 0.01)
    with r.store.tx() as c:
        a = r.budget.reserve(c, mid, model, 300, 300, "a")
        b = r.budget.reserve(c, mid, model, 300, 300, "b")
    with r.store.tx() as c:
        assert (
            r.budget.settle(c, a["id"], {"prompt_tokens": 100, "completion_tokens": 50})
            == "settled"
        )
        assert r.budget.settle(c, b["id"], None) == "unknown"
        v = r.budget.summary(c)
        assert v["settled_usd"] == 0.00015 and v["unknown_usd"] == 0.0006
        with pytest.raises(DomainError):
            r.budget.settle(c, a["id"], {"prompt_tokens": 1, "completion_tokens": 1})


def test_bound_breach_locks_future_dispatch(app):
    r, mid, model = configured(app, 0.01)
    with r.store.tx() as c:
        a = r.budget.reserve(c, mid, model, 20, 20, "a")
    with r.store.tx() as c:
        r.budget.settle(c, a["id"], {"prompt_tokens": 100, "completion_tokens": 50})
        with pytest.raises(DomainError):
            r.budget.reserve(c, mid, model, 20, 20, "b")


def test_unlisted_disabled_and_unverified_models_fail_closed(app):
    r = app.state.research
    with r.store.tx() as c:
        for model in [
            r.settings.models[0],
            "deepseek-ai/DeepSeek-V4.1-Flash",
            "other/model",
        ]:
            with pytest.raises(DomainError):
                r.budget.verification(c, model)


def test_expired_verification_cannot_dispatch(app):
    r, mid, model = configured(app)
    with r.store.tx() as c:
        v = r.store.setting(c, "live_verification")
        v["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        r.store.set_setting(c, "live_verification", v)
        with pytest.raises(DomainError):
            r.budget.reserve(c, mid, model, 1, 1, "a")


def test_twenty_four_dollar_cap_includes_settled_unknown_and_held_work(app):
    # An older verification cannot raise the newly authorized aggregate limit.
    r, mid, model = configured(app, 25)
    with r.store.tx() as c:
        mission = r.store.get(c, mid, "mission")
        mission["brief"]["budget_usd"] = 24
        r.store.put(c, "mission", mission)
        settled = r.budget.reserve(c, mid, model, 14_000_000, 0, "settled")
        r.budget.settle(
            c, settled["id"], {"prompt_tokens": 14_000_000, "completion_tokens": 0}
        )
        uncertain = r.budget.reserve(c, mid, model, 5_000_000, 0, "uncertain")
        r.budget.unknown(c, uncertain["id"])
        r.budget.hold(c, mid, 5_000_000, "pending-schedule")
        summary = r.budget.summary(c)
        assert (
            summary["absolute_cap_usd"]
            == summary["authorized_cap_usd"]
            == summary["operational_cap_usd"]
            == 24
        )
        assert summary["settled_usd"] == 14
        assert summary["unknown_usd"] == summary["reserved_usd"] == 5
        assert summary["global_committed_usd"] == 24 and summary["remaining_usd"] == 0
        with pytest.raises(DomainError, match="Aggregate credit stop"):
            r.budget.reserve(c, mid, model, 1, 0, "one-more-microdollar")


def test_twenty_four_dollar_limit_is_atomic_across_missions(app):
    r, _, model = configured(app, 25)
    with r.store.tx() as c:
        mission_ids = []
        for _ in range(8):
            brief = demo_brief()
            brief["budget_usd"] = 24
            mission_ids.append(
                r.create_mission(c, MissionBrief.model_validate(brief))["id"]
            )

    def reserve(mid):
        try:
            with r.store.tx() as c:
                r.budget.reserve(c, mid, model, 3_000_000, 3_000_000, "attempt-" + mid)
            return True
        except DomainError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, mission_ids)) == 4
    with r.store.tx() as c:
        assert r.budget.summary(c)["global_committed_usd"] == 24


def test_reported_credit_is_separate_from_billing_verification(app):
    r = app.state.research
    with r.store.tx() as c:
        r.store.set_setting(
            c,
            "token_factory_spending_authority",
            {
                "reported_existing_credit_usd": 25,
                "authorized_cap_usd": 24,
                "reported_trial_credit_usd": 1,
                "origin": "user_reported",
            },
        )
        value = r.budget.summary(c)
        assert value["reported_existing_credit_usd"] == 25
        assert value["authorized_cap_usd"] == value["absolute_cap_usd"] == 24
        assert value["operational_cap_usd"] == 0
        assert not r.store.setting(c, "live_verification", {})
        for provider in ("direct_council", "openrouter_free"):
            assert r.budget.summary(c, provider=provider)["absolute_cap_usd"] == 0


def test_public_mission_and_council_allowances_cannot_exceed_twenty_four(client, app):
    from pydantic import ValidationError

    from zerowall.contracts import ChatCreate, LiveVerification

    brief = demo_brief()
    brief["budget_usd"] = 24.000001
    assert (
        client.post(
            "/api/missions", json=brief, headers={"Idempotency-Key": "over-cap"}
        ).status_code
        == 422
    )
    with pytest.raises(ValidationError):
        ChatCreate(
            prompt="Compare possible approaches",
            provider="nebius_token_factory",
            models=app.state.research.settings.models[:2],
            budget_usd=25,
        )
    assert (
        LiveVerification.model_json_schema()["properties"]["operational_cap_usd"][
            "maximum"
        ]
        == 24
    )
    assert (
        LiveVerification.model_json_schema()["properties"]["existing_credit_usd"][
            "maximum"
        ]
        == 25
    )
