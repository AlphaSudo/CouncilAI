"""Exact USD arithmetic and immutable, explicitly scoped public reference cards."""

from decimal import Decimal, InvalidOperation, localcontext

from .db import digest

CHECKED = "2026-10-19"
RATES = {
    ("groq", "openai/gpt-oss-120b"): (
        "0.15",
        "0.075",
        "0.60",
        "https://console.groq.com/docs/models",
    ),
    ("groq", "openai/gpt-oss-20b"): (
        "0.075",
        "0.0375",
        "0.30",
        "https://console.groq.com/docs/models",
    ),
    ("gemini", "gemini-3.5-flash-lite"): (
        "0.30",
        "0.03",
        "2.50",
        "https://ai.google.dev/gemini-api/docs/pricing",
    ),
    ("zai", "glm-4.7-flash"): (
        "0",
        "0",
        "0",
        "https://docs.z.ai/guides/overview/pricing",
    ),
}


def decimal(value):
    if isinstance(value, bool):
        raise ValueError("Boolean money value")  # noqa: TRY004 -- one numeric-validation error contract.
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Invalid money value") from None
    if (
        not number.is_finite()
        or number < 0
        or len(str(value)) > 100
        or (number and number.adjusted() > 12)
    ):
        raise ValueError("Money must be finite and nonnegative")
    return number


def price_card(provider, model):
    rates = RATES.get((provider, model))
    card = {
        "version": "price/1",
        "provider": provider,
        "model": model,
        "currency": "USD",
        "tier": "public_paid_standard_reference"
        if provider != "zai"
        else "public_free_generation",
        "account_applicability": "public_free_generation"
        if provider == "zai"
        else "not_established",
        "checked_at": CHECKED,
        "valid_until": "2026-11-19",
        "unit": "USD per 1,000,000 tokens",
        "rates": {
            "input_uncached": rates[0] if rates else None,
            "cache_read_input": rates[1] if rates else None,
            "billable_output": rates[2] if rates else None,
        },
        "source_url": rates[3]
        if rates
        else "https://docs.api.nvidia.com/nim/docs/product",
        "cache_write": "not_applicable"
        if provider in ("groq", "zai", "gemini")
        else "unknown",
        "context_brackets": [],
        "modality": "text",
        "service_class": "standard",
        "storage_rate_per_million_token_hours": "1" if provider == "gemini" else None,
    }
    card["id"] = "price_" + digest(card)[:24]
    return card


def _calculate(
    usage,
    card,
    provider_amount=None,
    *,
    currency="USD",
    modality="text",
    input_context=None,
    storage_token_hours=None,
    tools=(),
    algorithm_version="cost/2",
):
    counts, states = usage["categories"], usage["states"]
    lines, missing, errors = [], [], list(usage.get("errors", []))
    if currency != card.get("currency") or modality != card.get("modality", "text"):
        errors.append("Unsupported currency or modality")
    rates = dict(card.get("rates", {}))
    for bracket in sorted(
        card.get("context_brackets", []), key=lambda b: b["minimum_input"]
    ):
        if input_context is None:
            missing.append("context bracket")
        elif input_context >= bracket["minimum_input"]:
            rates.update(bracket["rates"])
    total = Decimal(0)
    for category, rate in rates.items():
        value = counts.get(category)
        if states.get(category) == "not_applicable":
            continue
        if value is None or rate is None:
            missing.append(category)
            lines.append(
                {
                    "category": category,
                    "tokens": value,
                    "rate": rate,
                    "amount_usd": None,
                    "state": states.get(category, "not_reported"),
                }
            )
            visible = counts.get("output_visible")
            if (
                algorithm_version != "cost/1"
                and category == "billable_output"
                and value is None
                and rate is not None
                and type(visible) is int
                and visible >= 0
            ):
                try:
                    known_output = Decimal(visible) * decimal(rate) / Decimal(1000000)
                    total += known_output
                    lines.append(
                        {
                            "category": "output_visible",
                            "tokens": visible,
                            "rate": str(rate),
                            "amount_usd": str(known_output),
                            "state": "known_subset",
                            "basis": "Known visible-output subset; full billable output remains unreported",
                        }
                    )
                except ValueError as error:
                    errors.append(str(error))
            continue
        try:
            if type(value) is not int or value < 0:
                raise ValueError("Invalid token count")
            amount = Decimal(value) * decimal(rate) / Decimal(1000000)
            total += amount
            lines.append(
                {
                    "category": category,
                    "tokens": value,
                    "rate": str(rate),
                    "amount_usd": str(amount),
                    "state": "known",
                }
            )
        except ValueError as error:
            errors.append(str(error))
    if storage_token_hours is not None:
        try:
            rate = card.get("storage_rate_per_million_token_hours")
            if rate is None:
                missing.append("storage")
            else:
                amount = decimal(storage_token_hours) * decimal(rate) / Decimal(1000000)
                total += amount
                lines.append(
                    {
                        "category": "storage",
                        "units": str(storage_token_hours),
                        "rate": rate,
                        "amount_usd": str(amount),
                    }
                )
        except ValueError as error:
            errors.append(str(error))
    for tool in tools:
        try:
            amount = decimal(tool["units"]) * decimal(tool["unit_price_usd"])
            total += amount
            lines.append({**tool, "category": "tool", "amount_usd": str(amount)})
        except (ValueError, KeyError):
            missing.append("tool")
    reported = None
    if provider_amount is not None:
        try:
            reported = str(decimal(provider_amount))
        except ValueError:
            errors.append("Invalid provider amount")
    any_known = any(x.get("amount_usd") is not None for x in lines)
    status = (
        "invalid"
        if errors
        else "partial_estimate"
        if missing and any_known
        else "unknown"
        if missing or not lines
        else "complete_estimate"
    )
    return {
        "version": algorithm_version,
        "price_card_id": card["id"],
        "currency": currency,
        "status": status,
        "known_subtotal_usd": str(total),
        "complete_total_usd": str(total) if status == "complete_estimate" else None,
        "provider_reported_amount_usd": reported,
        "invoice_verified": False,
        "view": "applicable_tariff_estimate"
        if card.get("account_applicability") == "public_free_generation"
        else "published_price_equivalent",
        "lines": lines,
        "missing": sorted(set(missing)),
        "errors": errors,
    }


def calculate(usage, card, provider_amount=None, **kwargs):
    with localcontext() as context:
        context.prec = 100
        return _calculate(usage, card, provider_amount, **kwargs)
