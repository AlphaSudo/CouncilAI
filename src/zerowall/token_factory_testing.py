"""Explicit existing-credit test authorization; never fabricates card settings."""

from datetime import UTC, datetime, timedelta

from .db import DomainError, now, uid
from .token_factory_prices import PRICE_CACHE_DAYS


def authorize(research, catalogue, *, origin):
    """Called only by an explicitly authorized operator, not on startup or by a model."""
    store = research.store
    selected = {x["model_id"]: x for x in catalogue["selected"]}
    models = research.settings.models
    if (
        set(models) != set(selected)
        or catalogue.get("account_catalog_get_status") != 200
    ):
        raise DomainError("Exact model catalog evidence is required", 412)
    for row in selected.values():
        if not all(
            type(row.get(key)) in (int, float) and 0 < row[key] <= 100
            for key in (
                "input_price_per_million_tokens",
                "output_price_per_million_tokens",
            )
        ):
            raise DomainError("Missing or invalid public tariff", 412)
    with store.tx() as c:
        authority = store.setting(c, "token_factory_spending_authority", {})
        if (
            authority.get("reported_existing_credit_usd", 0) < 25
            or authority.get("authorized_cap_usd") != 24
        ):
            raise DomainError(
                "The reported credit and $24 authority must be recorded first", 412
            )
        authority.update(
            id=uid("authority"),
            user_testing_authorized=True,
            testing_authorized_at=now(),
            testing_authorization_origin=origin,
        )
        store.set_setting(c, "token_factory_spending_authority", authority)
        record = {
            "id": uid("verification"),
            "authorization_mode": "existing_credit_testing",
            "user_testing_authorized": True,
            "authority_id": authority["id"],
            "existing_credit_usd": 25,
            "operational_cap_usd": 24,
            "credit_only_confirmed": True,
            "automatic_payments_disabled": None,
            "billing_evidence": "User reported $25 existing balance and expressly authorized their own testing within a $24 aggregate cap. Card settings are unknown and were not changed.",
            "catalog_model_ids": models,
            "prices": {
                mid: {
                    "input": selected[mid]["input_price_per_million_tokens"],
                    "output": selected[mid]["output_price_per_million_tokens"],
                }
                for mid in models
            },
            "cached_input_prices": {
                mid: row["input_cached_price_per_million_tokens"]
                for mid, row in selected.items()
                if "input_cached_price_per_million_tokens" in row
            },
            "price_source": catalogue["source"],
            "price_checked_at": catalogue["checked_at"],
            "token_bound_verified": True,
            "token_bound_evidence": "Text-only input is reserved from the complete serialized UTF-8 JSON request plus 4096 framing bytes, multiplied by 2, at uncached tariffs regardless of request size. Context admission separately uses published model tokenizers within a 262144-token input/output window. max_completion_tokens includes visible and reasoning tokens.",
            "all_billing_categories_bounded": True,
            "additional_billed_output_tokens": 0,
            "billed_input_multiplier": 2,
            "verified_at": now(),
            "expires_at": (
                datetime.now(UTC) + timedelta(days=PRICE_CACHE_DAYS)
            ).isoformat(),
            "price_cache_days": PRICE_CACHE_DAYS,
            "origin": origin,
            "invoice_verified": False,
            "account_payment_settings_verified": False,
        }
        store.set_setting(c, "live_verification", record)
        store.event(
            c,
            "spending-policy",
            "token_factory.user_testing_authorized",
            {
                "verification_id": record["id"],
                "authority_id": authority["id"],
                "operational_cap_usd": 24,
                "card_settings": "unknown",
                "models": models,
                "origin": origin,
            },
        )
    return record
