"""Reserve a bounded final request before optional review; this is not a chat cap."""

import json
import math

from .budget import cost_micro, micro, mission_cap_micro
from .db import DomainError, digest

# A funding envelope, not an input limit. The actual final request can expand it
# transactionally under the unchanged cap; the 262K context window is independent.
ANNOTATION_FUNDING_HEADROOM_BYTES = 131072


def finishing_hold(council, c, chat, turn):
    if (
        chat["provider"] != "nebius_token_factory"
        or chat["protocol"]["version"] != "reviewed_v4"
    ):
        return None
    record = council.review.record(c, chat)
    if turn["phase"] == "opening":
        return None
    final = next(
        t for t in council.review.schedule(chat, record) if t["phase"] == "synthesis"
    )
    key = "finishing_" + digest([chat["id"], final["key"]])[:28]
    previous = c.execute("SELECT body FROM records WHERE id=?", (key,)).fetchone()
    member = council.runtime.effective_turn(c, chat, final)["participant"]
    model = member["model"]
    verification = council.research.budget.verification(c, model)
    output = council.output_limit(chat, final)
    final_prompt, _ids = council.review.prompt(
        c, chat, council.messages(c, chat), final
    )
    projected_request = council.research.provider.request(final_prompt, output, model)
    # Re-evaluate the real saved packet before each optional turn. A whole-window
    # hold needlessly stranded short requests with a small explicit allowance.
    # This allowance forecasts metadata growth; it is never an input/output cap.
    envelope_bytes = (
        len(json.dumps(projected_request, ensure_ascii=False).encode())
        + ANNOTATION_FUNDING_HEADROOM_BYTES
    )
    input_bound = math.ceil(
        (envelope_bytes + 4096) * verification["billed_input_multiplier"]
    )
    maximum = cost_micro(
        input_bound,
        output + verification["additional_billed_output_tokens"],
        verification["prices"][model],
    )
    if previous:
        item = council.store.get(c, key, "finishing_reserve")
        held = c.execute(
            "SELECT state FROM reservations WHERE id=?", (item["hold_id"],)
        ).fetchone()
        if held and held[0] == "held" and item["model"] == model:
            expand_final_hold(
                council.research.provider,
                c,
                chat["mission_id"],
                f"chat:{chat['id']}:{final['key']}",
                item["hold_id"],
                input_bound,
                output + verification["additional_billed_output_tokens"],
                verification,
            )
            item.update(
                funding_envelope_bytes=envelope_bytes,
                input_bound=input_bound,
                maximum_microusd=max(item["maximum_microusd"], maximum),
            )
            council.store.put(c, "finishing_reserve", item)
            return item
        council.research.budget.release_hold(c, item["hold_id"])
    hold_id = council.research.budget.hold(c, chat["mission_id"], maximum, key)
    item = {
        "id": key,
        "mission_id": chat["mission_id"],
        "chat_id": chat["id"],
        "review_cycle": record["cycle"],
        "hold_id": hold_id,
        "model": model,
        "turn_key": final["key"],
        "maximum_microusd": maximum,
        "funding_envelope_bytes": envelope_bytes,
        "input_bound": input_bound,
        "output_bound": output,
        "prices": verification["prices"][model],
        "verification_id": verification["id"],
        "context_tokens": council.settings.token_factory_generation["context_tokens"],
        "status": "held",
    }
    council.store.put(c, "finishing_reserve", item)
    return item


def expand_final_hold(
    provider, c, mission_id, purpose, hold_id, input_bound, output_bound, verification
):
    if not hold_id or not purpose.startswith("chat:"):
        return
    matching = [
        item
        for item in provider.store.list(c, "finishing_reserve", mission_id)
        if item["hold_id"] == hold_id
    ]
    if not matching:
        return  # Historical full-schedule holds retain their exact admission rules.
    row = c.execute(
        "SELECT maximum_microusd,state FROM reservations WHERE id=? AND mission_id=?",
        (hold_id, mission_id),
    ).fetchone()
    if not row or row["state"] != "held":
        raise DomainError("The finishing reservation is unavailable", 402)
    maximum = cost_micro(
        input_bound, output_bound, verification["prices"][matching[-1]["model"]]
    )
    extra = max(0, maximum - row["maximum_microusd"])
    if not extra:
        return
    total = provider.budget.summary(c)
    local = provider.budget.summary(c, mission_id)
    mission = provider.store.get(c, mission_id, "mission")
    committed = micro(
        local["settled_usd"] + local["reserved_usd"] + local["unknown_usd"]
    )
    if extra > micro(total["remaining_usd"]) or committed + extra > mission_cap_micro(
        mission
    ):
        raise DomainError(
            "The expanded final request does not fit existing credit; saved answers remain available",
            402,
        )
    c.execute(
        "UPDATE reservations SET maximum_microusd=maximum_microusd+? WHERE id=? AND state='held'",
        (extra, hold_id),
    )
    provider.store.event(
        c,
        mission_id,
        "budget.finishing_reserve_expanded",
        {"hold_id": hold_id, "additional_microusd": extra},
    )


def release(council, c, chat):
    for item in council.store.list(c, "finishing_reserve", chat["mission_id"]):
        council.research.budget.release_hold(c, item["hold_id"])
