"""Operator-only restoration of an already completed public opening. No inference."""

from copy import deepcopy

from .db import DomainError, digest, now, uid


def restore_completed_opening(research, call_id):
    store, council = research.store, research.chat
    with store.tx() as c:
        call = store.get(c, call_id, "call")
        restoration_id = "receipt_restore_" + digest(call_id)[:24]
        if c.execute("SELECT 1 FROM records WHERE id=?", (restoration_id,)).fetchone():
            return store.get(c, restoration_id, "completion_restoration")["result"]
        if (
            call.get("provider") != "nebius_token_factory"
            or call.get("state") != "unknown"
            or call.get("error") != "DecodingError"
        ):
            raise DomainError(
                "Only a saved unknown Token Factory decoding failure can be restored",
                409,
            )
        artifact = store.get(c, call["artifact_id"], "artifact")
        receipt = research.artifacts.read(artifact)
        response = receipt.get("response", {})
        choice = (response.get("choices") or [{}])[0]
        content = choice.get("message", {}).get("content")
        usage = response.get("usage")
        if (
            receipt.get("http_status") != 200
            or choice.get("finish_reason") != "stop"
            or response.get("model") != call["model"]
            or digest(receipt.get("request")) != call["request_hash"]
            or not isinstance(content, str)
            or not content.strip()
            or not isinstance(usage, dict)
            or any(
                type(usage.get(key)) is not int or usage[key] < 0
                for key in ("prompt_tokens", "completion_tokens")
            )
        ):
            raise DomainError(
                "The artifact has no verified complete response and final usage; its charge stays unknown",
                409,
            )
        chats = store.list(c, "chat", call["mission_id"])
        if len(chats) != 1:
            raise DomainError("A single matching council is required", 409)
        chat = chats[0]
        if (
            chat["status"] not in ("failed", "paused", "interrupted")
            or c.execute(
                "SELECT 1 FROM jobs WHERE target_id=? AND state IN ('queued','running','waiting')",
                (chat["id"],),
            ).fetchone()
        ):
            raise DomainError(
                "The council must be idle before a saved reply is restored", 409
            )
        messages = council.messages(c, chat)
        turn = council.next_turn(chat, messages, c)
        if (
            not turn
            or turn["phase"] != "opening"
            or f"chat:{chat['id']}:{turn['key']}" != call["purpose"]
            or turn["participant"]["model"] != call["model"]
            or call.get("output_context_hash")
            != council.output_recovery.context_hash(c, chat)
            or any(m.get("call_id") == call_id for m in messages)
        ):
            raise DomainError(
                "The saved opening no longer matches the current unchanged council turn",
                409,
            )
        reservation = c.execute(
            "SELECT * FROM reservations WHERE id=? AND call_id=? AND mission_id=?",
            (call["reservation_id"], call_id, call["mission_id"]),
        ).fetchone()
        if not reservation or reservation["state"] != "unknown":
            raise DomainError("The original unknown reservation is required", 409)
        original_call = deepcopy(call)
        original_reservation = dict(reservation)
        prompt, context_ids = council.prompt(chat, messages, turn, c)
        # Re-enter settlement only after validating the immutable provider receipt;
        # both this transition and the final settlement commit atomically.
        c.execute(
            "UPDATE reservations SET state='reserved' WHERE id=? AND state='unknown'",
            (call["reservation_id"],),
        )
        settled = research.budget.settle(c, call["reservation_id"], usage)
        if settled != "settled":
            raise DomainError(
                "Saved final usage could not settle the original reservation", 409
            )
        call.update(
            state="completed",
            settlement=settled,
            usage=usage,
            http_status=200,
            actual_model=response["model"],
            returned_model=response["model"],
            finish_reason="stop",
            local_restoration_id=restoration_id,
            original_error=call["error"],
            error=None,
            locally_restored_at=now(),
        )
        store.put(c, "call", call)
        research.accounting.settle(c, call)
        message_id = uid("message")
        public = research.artifacts.redact(content).strip()
        if chat.get("mode") == "reviewed":
            public = council.review.admit(c, chat, turn, public, message_id)
        message = council.message(
            c,
            chat,
            id=message_id,
            role="assistant",
            content=public,
            phase="opening",
            round=turn["round"],
            participant_id=turn["participant"]["id"],
            name=turn["participant"]["name"],
            model=call["model"],
            turn_key=turn["key"],
            review_cycle=turn.get("cycle"),
            outdated_context=False,
            ready=False,
            seen_user_sequence=max(
                (
                    m["sequence"]
                    for m in messages
                    if m["role"] == "user" and m["id"] in context_ids
                ),
                default=0,
            ),
            context_message_ids=context_ids,
            context_hash=digest(prompt),
            call_id=call_id,
            source="model_api",
            provider=call["provider"],
            actual_model=call["model"],
            partial=False,
            local_restoration_id=restoration_id,
        )
        chat.update(
            status="paused",
            active_turn=None,
            retry_wait=None,
            error=None,
            revision=chat["revision"] + 1,
        )
        step = store.get(c, chat["step_id"], "step")
        step.update(paused=True, status="committing")
        store.put(c, "step", step)
        store.put(c, "chat", chat)
        actual = c.execute(
            "SELECT actual_microusd FROM reservations WHERE id=?",
            (call["reservation_id"],),
        ).fetchone()[0]
        result = {
            "chat_id": chat["id"],
            "call_id": call_id,
            "message_id": message["id"],
            "status": "paused",
            "new_inference_calls": 0,
            "settled_estimate_usd": actual / 1e6,
            "released_unknown_hold_usd": (reservation["maximum_microusd"] - actual)
            / 1e6,
        }
        store.put(
            c,
            "completion_restoration",
            {
                "id": restoration_id,
                "mission_id": call["mission_id"],
                "artifact_id": artifact["id"],
                "artifact_sha256": artifact["sha256"],
                "origin": "trusted_operator_verified_complete_stream_receipt",
                "original_call": original_call,
                "original_reservation": original_reservation,
                "result": result,
            },
        )
        store.event(c, call["mission_id"], "call.completed_receipt_restored", result)
        return result
