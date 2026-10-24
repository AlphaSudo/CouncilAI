"""Integer micro-dollar accounting. Reservations precede every network request."""

from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
import json

from .db import DomainError, now, uid
from .free_limits import attempt_limit
from .spending_limits import TOKEN_FACTORY_CAP_USD


def micro(dollars):
    return int(
        (Decimal(str(dollars)) * 1_000_000).to_integral_value(rounding=ROUND_CEILING)
    )


def cost_micro(input_tokens, output_tokens, prices):
    return int(
        (
            Decimal(input_tokens) * Decimal(str(prices["input"]))
            + Decimal(output_tokens) * Decimal(str(prices["output"]))
        ).to_integral_value(rounding=ROUND_CEILING)
    )


def mission_cap_micro(mission):
    """Explicit credit amendments leave the original frozen brief intact."""
    if mission.get("spending_scope") == "shared_existing_credit":
        return micro(TOKEN_FACTORY_CAP_USD)
    return min(micro(TOKEN_FACTORY_CAP_USD), micro(mission["brief"]["budget_usd"]) + micro(mission.get("additional_authorized_credit_usd", 0)))


class Budget:
    def __init__(self, store, settings):
        self.store, self.settings = store, settings

    def summary(self, c, mission_id=None, provider="nebius_token_factory"):
        provider_filter = (
            "COALESCE(json_extract(body,'$.provider'),'nebius_token_factory')=?"
        )
        query = "SELECT * FROM reservations WHERE " + provider_filter
        args = (provider,)
        if mission_id:
            query += " AND mission_id=?"
            args += (mission_id,)
        rows = c.execute(query, args).fetchall()
        attempts = sum(json.loads(r["body"]).get("kind") != "undispatched_schedule_hold" for r in rows)
        settled = sum(
            r["actual_microusd"] or 0 for r in rows if r["state"] == "settled"
        )
        reserved = sum(
            r["maximum_microusd"] for r in rows if r["state"] in ("reserved", "held")
        )
        unknown = sum(r["maximum_microusd"] for r in rows if r["state"] == "unknown")
        verification = self.store.setting(c, "live_verification", {})
        authority = self.store.setting(c, "token_factory_spending_authority", {})
        authorized_cap = min(
            TOKEN_FACTORY_CAP_USD,
            self.settings.policy["budget"]["max_authorized_existing_credit_usd"],
            authority.get("authorized_cap_usd", TOKEN_FACTORY_CAP_USD),
        )
        cap = min(
            authorized_cap,
            verification.get("operational_cap_usd", 0),
            verification.get("existing_credit_usd", 0),
        )
        if provider in ("openrouter_free", "direct_council"):
            cap = 0
        global_total = c.execute(
            "SELECT COALESCE(SUM(CASE WHEN state='settled' THEN actual_microusd ELSE maximum_microusd END),0) FROM reservations WHERE "
            + provider_filter,
            (provider,),
        ).fetchone()[0]
        return {
            "settled_usd": settled / 1e6,
            "reserved_usd": reserved / 1e6,
            "unknown_usd": unknown / 1e6,
            "operational_cap_usd": cap,
            "absolute_cap_usd": 0
            if provider in ("openrouter_free", "direct_council")
            else TOKEN_FACTORY_CAP_USD,
            "authorized_cap_usd": 0
            if provider in ("openrouter_free", "direct_council")
            else authorized_cap,
            "reported_existing_credit_usd": authority.get(
                "reported_existing_credit_usd"
            )
            if provider == "nebius_token_factory"
            else None,
            "additional_payments_usd": 0,
            "global_committed_usd": global_total / 1e6,
            "remaining_usd": max(0, micro(cap) - global_total) / 1e6,
            "attempts": attempts,
            "provider": provider,
            **(
                {
                    "attempt_cap": attempt_limit(c, mission_id),
                    "remaining_calls": max(0, attempt_limit(c, mission_id) - attempts),
                }
                if provider in ("openrouter_free", "direct_council") and mission_id
                else {}
            ),
        }

    def verification(self, c, model):
        if self.store.remote and not self.store.setting(c, 'cloud_ledger_ready'):
            raise DomainError('Import the existing spending ledger before enabling cloud inference; the $24 cap is shared with prior usage', 412)
        v = self.store.setting(c, "live_verification", {})
        if not self.settings.api_key:
            raise DomainError("NEBIUS_API_KEY is missing", 412)
        if not v or datetime.fromisoformat(v["expires_at"]) <= datetime.now(UTC):
            raise DomainError(
                "Token Factory model prices need a refresh. Reconnect to refresh them; your chosen models and existing-credit limit are unchanged."
                if v.get("authorization_mode") == "existing_credit_testing"
                else "Current billing, price and token-bound verification is required", 412
            )
        if not self.funding_confirmed(c, v) or not all(
            v.get(k)
            for k in (
                "credit_only_confirmed",
                "token_bound_verified",
                "all_billing_categories_bounded",
            )
        ):
            raise DomainError(
                "Credit-only billing and all charged categories must be verified", 412
            )
        if (
            model not in self.settings.models
            or model not in v["catalog_model_ids"]
            or model not in v["prices"]
        ):
            raise DomainError("Model is unavailable or has no verified price", 412)
        return v

    def funding_confirmed(self, c, verification):
        if verification.get("authorization_mode") != "existing_credit_testing":
            return bool(verification.get("automatic_payments_disabled"))
        authority = self.store.setting(c, "token_factory_spending_authority", {})
        return bool(
            authority.get("user_testing_authorized") is True
            and bool(authority.get("id"))
            and verification.get("user_testing_authorized") is True
            and verification.get("authority_id") == authority.get("id")
            and authority.get("additional_payment_authority_usd") == 0
            and 0
            < verification.get("operational_cap_usd", 0)
            <= authority.get("authorized_cap_usd", 0)
            <= 24
            and authority.get("reported_existing_credit_usd", 0)
            >= verification.get("existing_credit_usd", 0)
            > authority.get("authorized_cap_usd", 0)
        )

    def is_verified(self, c, model):
        try:
            self.verification(c, model)
            return True
        except DomainError:
            return False

    def reserve(
        self, c, mission_id, model, input_bound, output_bound, call_id, hold_id=None
    ):
        v = self.verification(c, model)
        prices = v["prices"][model]
        maximum = cost_micro(input_bound, output_bound, prices)
        if maximum <= 0:
            raise DomainError("A positive conservative request bound is required", 412)
        if hold_id:
            hold = c.execute(
                "SELECT * FROM reservations WHERE id=? AND mission_id=? AND state='held'",
                (hold_id, mission_id),
            ).fetchone()
            if not hold or hold["maximum_microusd"] < maximum:
                raise DomainError("Approved schedule reservation is insufficient", 402)
            c.execute(
                "UPDATE reservations SET maximum_microusd=maximum_microusd-? WHERE id=?",
                (maximum, hold_id),
            )
        mission = self.store.get(c, mission_id, "mission")
        global_summary = self.summary(c)
        local_summary = self.summary(c, mission_id)
        local_total = micro(
            local_summary["settled_usd"]
            + local_summary["reserved_usd"]
            + local_summary["unknown_usd"]
        )
        if maximum + micro(global_summary["global_committed_usd"]) > micro(
            global_summary["operational_cap_usd"]
        ):
            raise DomainError("Aggregate credit stop reached", 402)
        if maximum + local_total > mission_cap_micro(mission):
            raise DomainError("Mission allowance exhausted", 402)
        rid = uid("reservation")
        body = {
            "id": rid,
            "call_id": call_id,
            "model": model,
            "input_bound": input_bound,
            "output_bound": output_bound,
            "prices": prices,
            "verification_id": v["id"],
            "created_at": now(),
        }
        from .db import canonical

        c.execute(
            "INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",
            (rid, mission_id, call_id, maximum, None, "reserved", canonical(body)),
        )
        self.store.event(
            c,
            mission_id,
            "budget.reserved",
            {"reservation_id": rid, "maximum_usd": maximum / 1e6, "model": model},
        )
        return body

    def hold(self, c, mission_id, maximum, call_id):
        from .db import canonical

        global_summary = self.summary(c)
        local = self.summary(c, mission_id)
        m = self.store.get(c, mission_id, "mission")
        if maximum + micro(global_summary["global_committed_usd"]) > micro(
            global_summary["operational_cap_usd"]
        ):
            raise DomainError(
                "Full schedule maximum does not fit remaining existing-credit allowance",
                402,
            )
        if maximum + micro(
            local["settled_usd"] + local["reserved_usd"] + local["unknown_usd"]
        ) > mission_cap_micro(m):
            raise DomainError(
                "Full schedule maximum does not fit mission allowance", 402
            )
        rid = uid("hold")
        c.execute(
            "INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",
            (
                rid,
                mission_id,
                call_id,
                maximum,
                None,
                "held",
                canonical({"kind": "undispatched_schedule_hold", "created_at": now()}),
            ),
        )
        self.store.event(
            c,
            mission_id,
            "budget.schedule_reserved",
            {"id": rid, "maximum_usd": maximum / 1e6},
        )
        return rid

    def release_hold(self, c, rid):
        c.execute(
            "UPDATE reservations SET maximum_microusd=0,actual_microusd=0,state='released' WHERE id=? AND state='held'",
            (rid,),
        )

    def settle(self, c, rid, usage):
        import json

        row = c.execute("SELECT * FROM reservations WHERE id=?", (rid,)).fetchone()
        if not row or row["state"] != "reserved":
            raise DomainError("Reservation cannot be settled twice")
        body = json.loads(row["body"])
        if not usage or not all(
            isinstance(usage.get(k), int)
            and not isinstance(usage.get(k), bool)
            and usage[k] >= 0
            for k in ("prompt_tokens", "completion_tokens")
        ):
            c.execute("UPDATE reservations SET state='unknown' WHERE id=?", (rid,))
            return "unknown"
        actual = cost_micro(
            usage["prompt_tokens"], usage["completion_tokens"], body["prices"]
        )
        reported = usage.get("cost")
        if isinstance(reported, (int, float)) and not isinstance(reported, bool):
            import math

            if math.isfinite(reported) and reported >= 0:
                actual = max(actual, micro(reported))
        if (
            usage["prompt_tokens"] > body["input_bound"]
            or usage["completion_tokens"] > body["output_bound"]
            or actual > row["maximum_microusd"]
        ):
            # Record actual charge even when an asserted external bound was wrong, then lock further calls.
            verification = self.store.setting(c, "live_verification", {})
            verification["all_billing_categories_bounded"] = False
            self.store.set_setting(c, "live_verification", verification)
            self.store.event(
                c,
                row["mission_id"],
                "budget.bound_breached",
                {"reservation_id": rid, "actual_usd": actual / 1e6},
            )
        c.execute(
            "UPDATE reservations SET actual_microusd=?,state='settled' WHERE id=?",
            (actual, rid),
        )
        self.store.event(
            c,
            row["mission_id"],
            "budget.settled",
            {"reservation_id": rid, "actual_usd": actual / 1e6},
        )
        return "settled"

    def unknown(self, c, rid):
        c.execute(
            "UPDATE reservations SET state='unknown' WHERE id=? AND state='reserved'",
            (rid,),
        )
