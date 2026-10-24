"""Refresh public tariffs, never renew or expand the user's spending authority."""

import math
import threading
from datetime import UTC, datetime, timedelta

import httpx

from .db import now, uid

PRICE_CACHE_DAYS = 7
PRICE_SOURCE = "https://tokenfactory.nebius.com/api/public/models_info"
_locks = {}
_lock_guard = threading.Lock()


def catalogue(settings):
    """Two metadata GETs; no completion, reservation or inference endpoint."""
    with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as client:
        public = client.get(PRICE_SOURCE)
        public.raise_for_status()
        account = client.get(
            settings.base_url + "/models",
            headers={"Authorization": "Bearer " + settings.api_key},
        )
        account.raise_for_status()
    available = {row["id"] for row in account.json()["data"]}
    rows = public.json()
    if not isinstance(rows, list):
        raise TypeError("Invalid public tariff response")
    selected = {}
    for group in rows:
        for row in [group] if "model_id" in group else group.get("flavors", []):
            mid = row.get("model_id")
            if mid not in settings.models or mid not in available:
                continue
            for field in (
                "input_price_per_million_tokens",
                "output_price_per_million_tokens",
            ):
                value = row.get(field)
                if (
                    type(value) not in (int, float)
                    or not math.isfinite(value)
                    or not 0 < value <= 100
                ):
                    raise ValueError("Invalid public tariff")
            if mid in selected and any(
                selected[mid].get(k) != row.get(k)
                for k in (
                    "input_price_per_million_tokens",
                    "output_price_per_million_tokens",
                    "input_cached_price_per_million_tokens",
                )
            ):
                raise ValueError("Conflicting model tariffs")
            selected[mid] = row
    if not selected:
        raise ValueError("No configured models have current tariffs")
    return {
        "checked_at": now(),
        "source": PRICE_SOURCE,
        "account_catalog_get_status": account.status_code,
        "account_model_ids": sorted(available),
        "selected": list(selected.values()),
    }


def refresh_prices(research, *, force=False):
    """Reuse an existing grant; expired/missing/revoked grants are never invented."""
    if not research.settings.api_key:
        return
    with _lock_guard:
        lock = _locks.setdefault(str(research.store.path), threading.Lock())
    with lock:
        with research.store.tx() as c:
            previous = research.store.setting(c, "live_verification", {})
            if (
                previous.get("authorization_mode") != "existing_credit_testing"
                or not research.budget.funding_confirmed(c, previous)
                or not all(
                    previous.get(k)
                    for k in (
                        "credit_only_confirmed",
                        "token_bound_verified",
                        "all_billing_categories_bounded",
                    )
                )
            ):
                return
            try:
                fresh = datetime.fromisoformat(previous["expires_at"]) > datetime.now(
                    UTC
                )
            except (KeyError, ValueError, TypeError):
                fresh = False
            if not force and fresh:
                return
            last = research.store.setting(c, "token_factory_price_refresh", {})
            if not force and last.get("retry_after", "") > now():
                return
        # Network I/O stays outside the SQLite transaction.
        try:
            evidence = catalogue(research.settings)
            selected = {row["model_id"]: row for row in evidence["selected"]}
            prices = {
                mid: {
                    "input": row["input_price_per_million_tokens"],
                    "output": row["output_price_per_million_tokens"],
                }
                for mid, row in selected.items()
            }
            cached = {
                mid: row["input_cached_price_per_million_tokens"]
                for mid, row in selected.items()
                if type(row.get("input_cached_price_per_million_tokens"))
                in (int, float)
                and math.isfinite(row["input_cached_price_per_million_tokens"])
                and 0
                <= row["input_cached_price_per_million_tokens"]
                <= prices[mid]["input"]
            }
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            with research.store.tx() as c:
                research.store.set_setting(
                    c,
                    "token_factory_price_refresh",
                    {
                        "state": "unavailable",
                        "checked_at": now(),
                        "error": type(error).__name__,
                        "retry_after": (
                            datetime.now(UTC) + timedelta(seconds=60)
                        ).isoformat(),
                        "message": "Token Factory's connection and prices could not be refreshed. Your chosen models are preserved.",
                    },
                )
            return
        with research.store.tx() as c:
            current = research.store.setting(c, "live_verification", {})
            if current.get("id") != previous.get(
                "id"
            ) or not research.budget.funding_confirmed(c, current):
                return  # A concurrent grant change cannot be undone by a refresh.
            artifact = research.artifacts.write(
                "spending-policy", "metadata_catalogue", evidence
            )
            research.store.put(c, "artifact", artifact)
            refreshed = {
                **current,
                "id": uid("verification"),
                "catalog_model_ids": list(selected),
                "prices": prices,
                "cached_input_prices": cached,
                "price_source": PRICE_SOURCE,
                "price_checked_at": evidence["checked_at"],
                "verified_at": now(),
                "expires_at": (
                    datetime.now(UTC) + timedelta(days=PRICE_CACHE_DAYS)
                ).isoformat(),
                "price_cache_days": PRICE_CACHE_DAYS,
                "metadata_artifact_id": artifact["id"],
            }
            research.store.set_setting(c, "live_verification", refreshed)
            research.store.set_setting(
                c,
                "token_factory_price_refresh",
                {"state": "ready", "checked_at": now(), "cache_days": PRICE_CACHE_DAYS},
            )
            research.store.event(
                c,
                "spending-policy",
                "token_factory.prices_refreshed",
                {
                    "previous_verification_id": current["id"],
                    "verification_id": refreshed["id"],
                    "authority_id": current.get("authority_id"),
                    "cache_days": PRICE_CACHE_DAYS,
                    "artifact_id": artifact["id"],
                    "new_inference_calls": 0,
                },
            )
