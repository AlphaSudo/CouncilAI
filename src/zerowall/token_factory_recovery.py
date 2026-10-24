"""Explicit same-chat continuation after an unanswered opening."""

from .budget import micro, mission_cap_micro
from .db import DomainError, digest, now

LIGHTNING = "nvidia/Nemotron-3_5-Lightning"


def preview(council, c, chat):
    if (
        chat["provider"] != "nebius_token_factory"
        or chat.get("protocol", {}).get("version") not in ("reviewed_v3", "reviewed_v4")
        or chat["status"] not in ("failed", "unavailable", "interrupted", "paused")
    ):
        return None
    if c.execute(
        "SELECT 1 FROM jobs WHERE target_id=? AND state IN ('queued','running')",
        (chat["id"],),
    ).fetchone():
        return None
    turn = council.next_turn(chat, council.messages(c, chat), c)
    if not turn or turn["phase"] != "opening":
        return None
    purpose = f"chat:{chat['id']}:{turn['key']}"
    calls = [
        call
        for call in council.store.list(c, "call", chat["mission_id"])
        if call.get("purpose") == purpose
    ]
    call = calls[-1] if calls else None
    if not call:
        return None
    timed_out = call.get("state") == "unknown"
    reasoning_only = False
    if call.get("state") == "completed" and call.get("finish_reason") == "length":
        from .usage import normalize

        usage = normalize(chat["provider"], call.get("usage"))["categories"]
        reasoning_only = bool(
            usage.get("output_reasoning") and usage.get("output_visible") == 0
        )
        if reasoning_only:
            try:
                reasoning_only = not council.output_recovery.draft(c, call).strip()
            except (DomainError, OSError, ValueError, KeyError):
                return None
    if not timed_out and not reasoning_only:
        return None
    members = [
        p for p in council.active_members(chat) if p["id"] != turn["participant"]["id"]
    ]
    if len(members) < 2:
        return None
    mission = council.store.get(c, chat["mission_id"], "mission")
    local = council.research.budget.summary(c, chat["mission_id"])
    used = sum(
        micro(local[key]) for key in ("settled_usd", "reserved_usd", "unknown_usd")
    )
    # Quote enough uncommitted authority for the remaining review. This is an
    # allowance, not a charge; every actual request still reserves independently.
    shortfall = max(0, micro(0.25) - max(0, mission_cap_micro(mission) - used))
    extra = ((shortfall + 9999) // 10000) * 10000
    reason = None
    if extra > micro(local["remaining_usd"]) or mission_cap_micro(
        mission
    ) + extra > micro(24):
        reason = "The additional conversation allowance does not fit the remaining $24 existing-credit authority."
    try:
        for participant in members:
            council.research.budget.verification(c, participant["model"])
        council.research.provider.capacity(
            c,
            chat["mission_id"],
            required=council.remaining(chat, council.messages(c, chat), c),
        )
    except DomainError as error:
        reason = error.message
    return {
        "call_id": call["id"],
        "member_id": turn["participant"]["id"],
        "name": turn["participant"]["name"],
        "model": turn["participant"]["model"],
        "action_label": "Continue without "
        + (
            "Lightning"
            if turn["participant"]["model"] == LIGHTNING
            else turn["participant"]["name"]
        ),
        "allowed": reason is None,
        "reason": reason,
        "additional_allowance_usd": extra / 1e6,
        "conversation_allowance_usd": (mission_cap_micro(mission) + extra) / 1e6,
        "remaining_models": [p["model"] for p in members],
        "unknown_charge_retained": timed_out,
        "failure_kind": "reasoning_only_output_limit"
        if reasoning_only
        else "opening_interrupted",
    }


def continue_without_model(council, c, chat, body):
    quote = preview(council, c, chat)
    if not quote or body.recovery_call_id != quote["call_id"]:
        raise DomainError(
            "The timed-out opening changed. Refresh before continuing.", 409
        )
    if not quote["allowed"]:
        raise DomainError(quote["reason"], 402)
    if (
        quote["unknown_charge_retained"]
        and not body.authorize_retry_with_unknown_charge
    ):
        raise DomainError(
            "Acknowledge that the earlier unknown charge remains counted before continuing.",
            409,
        )
    if micro(body.additional_allowance_usd) != micro(quote["additional_allowance_usd"]):
        raise DomainError(
            "Approve the displayed additional conversation allowance before continuing.",
            409,
        )
    mission = council.store.get(c, chat["mission_id"], "mission")
    old_cap = mission_cap_micro(mission)
    if body.additional_allowance_usd:
        mission["additional_authorized_credit_usd"] = (
            micro(mission.get("additional_authorized_credit_usd", 0))
            + micro(body.additional_allowance_usd)
        ) / 1e6
        council.store.put(c, "mission", mission)
        council.store.event(
            c,
            chat["mission_id"],
            "budget.conversation_allowance_added",
            {
                "chat_id": chat["id"],
                "actor": "human_director",
                "failed_call_id": quote["call_id"],
                "old_allowance_usd": old_cap / 1e6,
                "added_allowance_usd": body.additional_allowance_usd,
                "new_allowance_usd": mission_cap_micro(mission) / 1e6,
                "aggregate_cap_usd": 24,
            },
        )
    missing = {
        "model": quote["model"],
        "name": quote["name"],
        "phase": "opening",
        "call_id": quote["call_id"],
        "kind": "director_excluded",
        "reason": f"The director continued with the other selected models after {quote['name']}'s unanswered opening. Its recorded cost or unknown-charge hold remains counted.",
    }
    chat.setdefault("unavailable_members", {})[quote["member_id"]] = missing
    chat.update(active_turn=None, retry_wait=None)
    chat.pop("pending_request_recovery", None)
    record = council.review.record(c, chat)
    members = council.active_members(chat)
    engine = council.review.engine(chat)
    roles = engine.roles_for(members)
    for phase, participant in list(record["roles"].items()):
        if participant == quote["member_id"]:
            record["roles"][phase] = roles[phase]
            record["reassignments"].append(
                {
                    "phase": phase,
                    "participant_id": roles[phase],
                    "original_author_id": None,
                    "actor": "human_director",
                    "reason": "Continue without the selected member's unanswered opening",
                    "at": now(),
                }
            )
    record["roles_hash"] = digest(record["roles"])
    record["partial_reasons"].append(missing["reason"])
    record["revision"] += 1
    engine.save_plan(c, chat, record)
    council.message(
        c,
        chat,
        role="system",
        name="Council",
        phase="participation_change",
        content=(
            f"Continuing this conversation without {quote['name']}. Completed answers remain saved; "
            "recorded costs and unknown-charge holds remain counted. Its absence does not imply agreement. "
            + (
                f"The director added ${body.additional_allowance_usd:.2f} to this conversation's existing-credit allowance within the $24 aggregate cap."
                if body.additional_allowance_usd
                else "No additional conversation allowance was added."
            )
        ),
        source="human_director",
    )
    council.store.event(
        c,
        chat["mission_id"],
        "chat.member_excluded",
        {
            "chat_id": chat["id"],
            "actor": "human_director",
            "member_id": quote["member_id"],
            "model": quote["model"],
            "failed_call_id": quote["call_id"],
            "retry_dispatched": False,
        },
    )
