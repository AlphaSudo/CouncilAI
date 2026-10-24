"""Append-only accounting enrichment; old call/publication records stay untouched."""

import re
from decimal import Decimal

from .db import digest, now
from .pricing import calculate, price_card
from .response_timing import summarize
from .token_factory_generation import observe_reasoning_budget
from .usage import normalize


class Accounting:
    def __init__(self, research):
        self.research, self.store = research, research.store

    def freeze(self, c, call):
        card = price_card(call["provider"], call["model"])
        if call["provider"] == "nebius_token_factory":
            v = self.research.budget.verification(c, call["model"])
            prices = v["prices"][call["model"]]
            cached = v.get("cached_input_prices", {}).get(call["model"])
            card.update(
                tier="token_factory_public_text",
                account_applicability="published_reference_not_invoice",
                checked_at=v.get("price_checked_at", v.get("verified_at", "")[:10]),
                source_url=v.get("price_source", ""),
                rates={
                    "input_uncached": str(prices["input"]),
                    "cache_read_input": str(cached) if cached is not None else None,
                    "billable_output": str(prices["output"]),
                },
                cache_write="not_applicable",
                verification_id=v["id"],
            )
            if cached is None:
                card["rates"] = {
                    "input_total_reported": str(prices["input"]),
                    "billable_output": str(prices["output"]),
                }
                card["input_pricing"] = (
                    "Flat published input rate; no separate cached tariff advertised"
                )
            card["id"] = (
                "price_"
                + digest({k: value for k, value in card.items() if k != "id"})[:24]
            )
        if not c.execute("SELECT 1 FROM records WHERE id=?", (card["id"],)).fetchone():
            self.store.put(c, "price_card", {**card, "mission_id": "pricing"})
        call["price_card_id"] = card["id"]
        call["cost_algorithm_version"] = "cost/2"
        call["logical_turn_id"] = call.get("logical_turn_id") or call.get(
            "purpose", call["id"]
        )

    def attempt(self, c, call):
        usage = normalize(call.get("provider"), call.get("usage"))
        card = (
            self.store.get(c, call["price_card_id"], "price_card")
            if call.get("price_card_id")
            else price_card(call.get("provider"), call.get("model"))
        )
        requested_card = card
        snapshot_hash = digest(call)
        for previous in reversed(
            self.store.list(c, "usage_record", call["mission_id"])
        ):
            if previous["call_id"] != call["id"]:
                continue
            if previous.get("call_snapshot_hash") == snapshot_hash:
                return previous
            if (
                not previous.get("call_snapshot_hash")
                and previous["usage"]["raw_hash"] == usage["raw_hash"]
                and previous["state"] == call.get("state")
                and previous["model"]
                == (call.get("returned_model") or call.get("model"))
                and previous["price_card"]["id"] == card["id"]
                and previous["cost"]["provider_reported_amount_usd"]
                == (str(call["cost_usd"]) if call.get("cost_usd") is not None else None)
            ):
                return previous
        returned = call.get("returned_model")
        if isinstance(returned, str) and returned.removeprefix("private/") != call.get(
            "model"
        ):
            card = price_card(call.get("provider"), returned.removeprefix("private/"))
        return {
            "id": "usage_"
            + digest(
                {
                    "call": call,
                    "version": usage["version"],
                    "card": card["id"],
                    "calculator": call.get("cost_algorithm_version", "cost/2"),
                }
            )[:24],
            "mission_id": call["mission_id"],
            "call_id": call["id"],
            "call_snapshot_hash": snapshot_hash,
            "logical_turn_id": call.get(
                "logical_turn_id", call.get("purpose", call["id"])
            ),
            "provider": call.get("provider"),
            "model": call.get("returned_model") or call.get("model"),
            "state": call.get("state"),
            "attempt_class": call.get("attempt_class", "base_or_recovery"),
            "artifact_id": call.get("artifact_id"),
            "usage": usage,
            "price_card": card,
            "requested_price_card_id": requested_card["id"],
            "price_notice": "Actual returned model differs from the dispatched card"
            if card["id"] != requested_card["id"]
            else "Rate expired; historical rate retained"
            if card.get("valid_until", "9999") < now()[:10]
            else None,
            "cost": calculate(
                usage,
                card,
                call.get("cost_usd"),
                algorithm_version=call.get("cost_algorithm_version", "cost/2"),
            ),
            "latency_ms": call.get("latency_ms"),
            "timing": summarize(call, usage),
            "historical_enrichment": not bool(call.get("price_card_id")),
            "context_pack_id": call.get("context_pack_id"),
            "generation": call.get("generation"),
            "reasoning_budget_observation": observe_reasoning_budget(call.get("generation"), usage),
        }

    def settle(self, c, call):
        self.research.tools.policy.settle_model(c, call)
        record = self.attempt(c, call)
        self.store.put(c, "usage_record", record)
        self.store.event(
            c,
            call["mission_id"],
            "accounting.updated",
            {"call_id": call["id"], "usage_record_id": record["id"]},
        )

    @staticmethod
    def total(attempts):
        unique = {a["call_id"]: a for a in attempts}.values()
        attempts = list(unique)
        categories = sorted({k for a in attempts for k in a["usage"]["categories"]})
        tokens = {
            k: {
                "known_subtotal": sum(
                    a["usage"]["categories"][k] or 0 for a in attempts
                ),
                "reported_attempts": sum(
                    a["usage"]["categories"][k] is not None for a in attempts
                ),
                "total_attempts": len(attempts),
            }
            for k in categories
        }
        reported = [
            Decimal(a["cost"]["provider_reported_amount_usd"])
            for a in attempts
            if a["cost"]["provider_reported_amount_usd"] is not None
        ]
        complete = sum(a["cost"]["status"] == "complete_estimate" for a in attempts)
        priced = sum(
            line.get("amount_usd") is not None
            for a in attempts
            for line in a["cost"]["lines"]
        )
        return {
            "attempts": len(attempts),
            "known_request_seconds": sum(
                a["timing"]["elapsed_seconds"]
                for a in attempts
                if a.get("timing", {}).get("elapsed_seconds") is not None
            ),
            "timed_attempts": sum(
                a.get("timing", {}).get("elapsed_seconds") is not None for a in attempts
            ),
            "usage_reported_attempts": sum(
                a["usage"]["status"] == "reported" for a in attempts
            ),
            "unknown_outcomes": sum(
                a["state"] in ("unknown", "dispatching") for a in attempts
            ),
            "tokens": tokens,
            "known_reference_subtotal_usd": str(
                sum(
                    (Decimal(a["cost"]["known_subtotal_usd"]) for a in attempts),
                    Decimal(0),
                )
            )
            if priced
            else None,
            "priced_components": priced,
            "complete_estimates": complete,
            "cost_state": "complete_estimate"
            if attempts and complete == len(attempts)
            else "partial_estimate"
            if attempts
            else "unknown",
            "provider_reported_subtotal_usd": str(sum(reported, Decimal(0)))
            if reported
            else None,
            "provider_reported_attempts": len(reported),
            "invoice_verified": False,
        }

    def projection(self, c, chat):
        calls = self.store.list(c, "call", chat["mission_id"])
        # Enrich historical projections without rewriting their saved call or
        # append-only accounting records. Missing old stream timings stay unknown.
        attempts = []
        for call in calls:
            attempt = dict(self.attempt(c, call))
            attempt["timing"] = summarize(call, attempt["usage"])
            attempt["reasoning_budget_observation"] = observe_reasoning_budget(call.get("generation"), attempt["usage"])
            attempts.append(attempt)
        groups = {}
        for item in attempts:
            groups.setdefault(item["logical_turn_id"], []).append(item)
        messages = self.store.list(c, "chat_message", chat["mission_id"])
        by_call = {a["call_id"]: a for a in attempts}
        ordinal = {a["call_id"]: index for index, a in enumerate(attempts)}
        replies = {}
        for message in messages:
            a = by_call.get(message.get("call_id"))
            if a:
                replies[message["id"]] = {
                    "attempts": groups[a["logical_turn_id"]],
                    "total": self.total(groups[a["logical_turn_id"]]),
                    "cumulative_through_reply": self.total(
                        attempts[: ordinal[a["call_id"]] + 1]
                    ),
                }

        def rollup(key):
            result = {}
            for attempt in attempts:
                value = key(attempt)
                result.setdefault(value, []).append(attempt)
            return {k: self.total(v) for k, v in result.items()}

        tools = self.store.list(c, "tool_invocation", chat["mission_id"])
        seq = c.execute(
            "SELECT COALESCE(MAX(seq),0) FROM events WHERE mission_id=?",
            (chat["mission_id"],),
        ).fetchone()[0]
        return {
            "version": "accounting/1",
            "as_of_sequence": seq,
            "attempts": attempts,
            "replies": replies,
            "by_provider": rollup(lambda a: str(a["provider"])),
            "by_model": rollup(lambda a: str(a["provider"]) + "::" + str(a["model"])),
            "by_cycle": rollup(
                lambda a: (
                    re.search(r":review:(\d+):", a["logical_turn_id"]).group(1)
                    if re.search(r":review:(\d+):", a["logical_turn_id"])
                    else "historical_or_discussion"
                )
            ),
            "total": self.total(attempts),
            "shared_research": {
                "invocations": len(tools),
                "external_credit_reservations": sum(
                    t.get("search_credits", 0) for t in tools if not t.get("reused")
                ),
                "unknown_outcomes": sum(t.get("state") == "unknown" for t in tools),
            },
            "generated_at": now(),
        }
