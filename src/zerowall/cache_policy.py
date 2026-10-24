"""Explicit caches remain closed without verified lifecycle and spending authority."""

from decimal import Decimal

from .db import DomainError
from .pricing import decimal


def economics(
    *,
    tokens=None,
    reuses=None,
    input_rate=None,
    read_rate=None,
    creation_cost=None,
    storage_cost=None,
    refresh_cost=None,
):
    values = [
        tokens,
        reuses,
        input_rate,
        read_rate,
        creation_cost,
        storage_cost,
        refresh_cost,
    ]
    if any(x is None for x in values):
        return {"status": "unknown", "benefit_usd": None, "admit": False}
    benefit = (
        decimal(tokens)
        * decimal(reuses)
        * (decimal(input_rate) - decimal(read_rate))
        / Decimal(1000000)
    )
    expenses = decimal(creation_cost) + decimal(storage_cost) + decimal(refresh_cost)
    return {
        "status": "estimated",
        "benefit_usd": str(benefit),
        "lifecycle_cost_usd": str(expenses),
        "profitable": benefit > expenses,
        "admit": False,
        "reason": "Explicit billable caches require separate lifecycle support and spending authority",
    }


def validate_handle(handle, *, provider, model, schema_hash, tools_hash, now):
    if (
        handle.get("provider") != provider
        or handle.get("model") != model
        or handle.get("schema_hash") != schema_hash
        or handle.get("tools_hash") != tools_hash
    ):
        raise DomainError("Cache namespace changed; no handle reused", 422)
    if handle.get("expires_at", "") <= now:
        raise DomainError("Cache expired; no automatic paid refresh", 412)
    raise DomainError(
        "Explicit provider caches are disabled under the current funding policy", 412
    )
