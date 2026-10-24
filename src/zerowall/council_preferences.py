"""Audited preferences and explicit existing-credit allowance amendments."""

from .budget import micro, mission_cap_micro
from .db import DomainError
from .thinking_levels import projection


class CouncilPreferences:
    def __init__(self, research):
        self.research, self.store = research, research.store

    def thinking(self, chat):
        if chat["provider"] != "nebius_token_factory":
            return {"supported": False}
        return projection(
            self.research.settings,
            [self.research.chat.runtime.effective_member(chat, p)["model"] for p in chat["participants"]],
            chat.get("thinking_level", "balanced"),
        )

    def set_thinking(self, c, cid, body):
        chat = self.store.get(c, cid, "chat")
        if chat["provider"] != "nebius_token_factory":
            raise DomainError(
                "These thinking presets currently support Token Factory councils", 422
            )
        old = chat.get("thinking_level", "balanced")
        chat.update(
            thinking_level=body.level,
            thinking_revision=chat.get("thinking_revision", 0) + 1,
        )
        self.store.put(c, "chat", chat)
        self.store.event(
            c,
            chat["mission_id"],
            "chat.thinking_changed",
            {
                "chat_id": cid,
                "before": old,
                "after": body.level,
                "applies_to": "requests_not_started_yet",
                "new_inference_calls": 0,
            },
        )
        return self.thinking(chat)

    def allowance(self, c, chat):
        if chat["provider"] != "nebius_token_factory":
            return None
        mission = self.store.get(c, chat["mission_id"], "mission")
        local = self.research.budget.summary(c, chat["mission_id"])
        total = self.research.budget.summary(c)
        committed = sum(
            micro(local[key]) for key in ("settled_usd", "reserved_usd", "unknown_usd")
        )
        cap = mission_cap_micro(mission)
        return {
            "scope": mission.get("spending_scope", "conversation"),
            "cap_usd": cap / 1e6,
            "committed_usd": committed / 1e6,
            "remaining_usd": min(max(0, cap - committed), micro(total["remaining_usd"])) / 1e6,
            "global_remaining_usd": total["remaining_usd"],
            "maximum_addition_usd": max(
                0, min(micro(24) - cap, micro(total["remaining_usd"]))
            )
            / 1e6,
            "absolute_cap_usd": 24,
            "additional_payments_usd": 0,
        }

    def share_cap(self, c, cid):
        chat = self.store.get(c, cid, "chat")
        if chat["provider"] != "nebius_token_factory":
            raise DomainError("Shared existing credit applies to Token Factory councils", 422)
        authority = self.store.setting(c, "token_factory_spending_authority", {})
        if authority.get("authorized_cap_usd") != 24 or authority.get("additional_payment_authority_usd") != 0:
            raise DomainError("The $24 existing-credit authority is required", 412)
        mission = self.store.get(c, chat["mission_id"], "mission")
        if mission.get("spending_scope") == "shared_existing_credit":
            return self.allowance(c, chat)
        previous = mission_cap_micro(mission) / 1e6
        mission["spending_scope"] = "shared_existing_credit"
        chat["spending_scope"] = "shared_existing_credit"
        self.store.put(c, "mission", mission)
        self.store.put(c, "chat", chat)
        self.store.event(c, chat["mission_id"], "budget.shared_cap_adopted", {
            "chat_id": cid, "actor": "human_director", "previous_chat_limit_usd": previous,
            "aggregate_cap_usd": 24, "new_inference_calls": 0,
        })
        return self.allowance(c, chat)

    def add_allowance(self, c, cid, body):
        chat = self.store.get(c, cid, "chat")
        value = self.allowance(c, chat)
        if value is None:
            raise DomainError(
                "Existing-credit allowances apply to Token Factory councils", 422
            )
        amount = micro(body.add_usd)
        if amount > micro(value["maximum_addition_usd"]):
            raise DomainError(
                "This addition exceeds the remaining existing-credit authority or the $24 cap. No work was scheduled.",
                402,
            )
        for participant in chat["participants"]:
            self.research.budget.verification(c, participant["model"])
        mission = self.store.get(c, chat["mission_id"], "mission")
        mission["additional_authorized_credit_usd"] = (
            micro(mission.get("additional_authorized_credit_usd", 0)) + amount
        ) / 1e6
        self.store.put(c, "mission", mission)
        self.store.event(
            c,
            chat["mission_id"],
            "budget.conversation_allowance_added",
            {
                "chat_id": cid,
                "actor": "human_director",
                "old_allowance_usd": value["cap_usd"],
                "added_allowance_usd": body.add_usd,
                "new_allowance_usd": mission_cap_micro(mission) / 1e6,
                "new_inference_calls": 0,
            },
        )
        return self.allowance(c, chat)
