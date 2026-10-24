"""Atomic resource admission. Cache discounts never increase spending authority."""

from datetime import UTC, datetime

from .db import DomainError, digest, now
from .free_limits import CHAT_MAX_ATTEMPTS
from .token_factory_generation import MAX_CONTEXT_TOKENS

DEFAULTS = {
    "input_tokens": 2500000,
    "output_tokens": 163840,
    "research_calls": 5,
    "search_credits": 3,
    "fetch_requests": 6,
    "fetch_bytes": 12 * 1024 * 1024,
    "local_reads": 12,
    "retrieved_bytes": 48 * 1024,
}


def limits(chat):
    search = {"search_credits": min(20, 2 * len(chat["participants"]) + 9)} if chat.get("web_search_policy") == "per-reply-search/1" else {}
    if chat["provider"] == "nebius_token_factory":
        # Token pools use the context estimate. The larger financial byte bound
        # remains separate and still reserves money at full uncached tariffs.
        return {
            **DEFAULTS,
            **search,
            "input_tokens": CHAT_MAX_ATTEMPTS * MAX_CONTEXT_TOKENS,
            "output_tokens": CHAT_MAX_ATTEMPTS * MAX_CONTEXT_TOKENS,
        }
    return {**DEFAULTS, **search}


class ResourcePolicy:
    def __init__(self, research):
        self.research, self.store = research, research.store

    def window(self, c, chat):
        mission = self.store.get(c, chat["mission_id"], "mission")
        return mission.get("direct_attempt_window", {}).get(
            "id", chat["id"] + ":" + str(chat.get("generation", 0))
        )

    def reserve(self, c, chat, kind, amount, key, *, logical_turn_id=None):
        if type(amount) is not int or amount < 0 or kind not in DEFAULTS:
            raise DomainError("Invalid resource reservation", 422)
        window = self.window(c, chat)
        scope = (
            logical_turn_id if kind in ("local_reads", "retrieved_bytes") else window
        )
        identifier = "resource_" + digest([chat["id"], window, kind, key])[:24]
        row = c.execute("SELECT 1 FROM records WHERE id=?", (identifier,)).fetchone()
        if row:
            existing = self.store.get(c, identifier, "resource_reservation")
            if existing["state"] != "released":
                return existing
        used = sum(
            x["amount"]
            for x in self.store.list(c, "resource_reservation", chat["mission_id"])
            if x["kind"] == kind and x["scope"] == scope and x["state"] != "released"
        )
        maximum = limits(chat)[kind]
        if kind == "research_calls":
            mission = self.store.get(c, chat["mission_id"], "mission")
            maximum = mission.get("direct_attempt_window", {}).get(
                "research_call_limit", maximum
            )
        if used + amount > maximum:
            raise DomainError(
                f"This request reached its {kind.replace('_', ' ')} limit. Saved work remains in this conversation.",
                429,
            )
        value = {
            "id": identifier,
            "mission_id": chat["mission_id"],
            "chat_id": chat["id"],
            "window": window,
            "scope": scope,
            "kind": kind,
            "amount": amount,
            "state": "reserved",
            "created_at": now(),
            "key": key,
        }
        self.store.put(c, "resource_reservation", value)
        return value

    def update(self, c, reservation, state):
        reservation = self.store.get(c, reservation["id"], "resource_reservation")
        reservation.update(state=state, updated_at=now())
        self.store.put(c, "resource_reservation", reservation)

    def settle_model(self, c, call):
        state = (
            "released"
            if call["state"] == "cancelled_undispatched"
            else "unknown"
            if call["state"] in ("unknown", "dispatching")
            else "consumed"
        )
        for item in self.store.list(c, "resource_reservation", call["mission_id"]):
            if item["key"] == call["id"] and item["kind"] in (
                "input_tokens",
                "output_tokens",
            ):
                self.update(c, item, state)

    def reserve_monthly_search(self, c, chat, key, amount=1):
        month = datetime.now(UTC).strftime("%Y-%m")
        rows = c.execute(
            "SELECT body FROM records WHERE kind='search_credit'"
        ).fetchall()
        import json

        used = sum(
            x["amount"]
            for r in rows
            if (x := json.loads(r[0]))["month"] == month and x["state"] != "released"
        )
        if type(amount) is not int or not 1 <= amount <= 2:
            raise DomainError("Invalid search credit reservation", 422)
        if used + amount > self.research.settings.search_monthly_limit:
            raise DomainError(
                "Local monthly free-search ceiling reached; use saved sources", 429
            )
        record = {
            "id": "searchcredit_" + digest([chat["id"], key])[:24],
            "mission_id": chat["mission_id"],
            "month": month,
            "amount": amount,
            "state": "reserved",
        }
        if c.execute("SELECT 1 FROM records WHERE id=?", (record["id"],)).fetchone():
            raise DomainError(
                "A search with this dispatch identity already exists; inspect its saved result",
                409,
            )
        self.store.put(c, "search_credit", record)
        return record

    def recover(self):
        with self.store.tx() as c:
            import json

            for row in c.execute(
                "SELECT kind,body FROM records WHERE kind IN ('tool_invocation','search_credit','resource_reservation')"
            ).fetchall():
                record = json.loads(row["body"])
                if record.get("state") in ("dispatching", "reserved"):
                    record["state"] = "unknown"
                    self.store.put(c, row["kind"], record)
