"""Restore a completed rejected review reply locally, leaving all charges intact."""

from .db import DomainError, digest, now, uid
from .review_admission import VERSION


def restore_completed_review(research, call_id):
    store, council = research.store, research.chat
    with store.tx() as c:
        call = store.get(c, call_id, "call")
        restoration_id = "review_restore_" + digest([call_id, VERSION])[:24]
        if c.execute("SELECT 1 FROM records WHERE id=?", (restoration_id,)).fetchone():
            return store.get(c, restoration_id, "review_reply_restoration")["result"]
        if (
            call.get("provider") != "nebius_token_factory"
            or call.get("state") != "completed"
            or call.get("finish_reason") != "stop"
            or call.get("http_status") != 200
            or call.get("actual_model") != call["model"]
        ):
            raise DomainError(
                "Only a completed, identified Token Factory review reply can be restored locally",
                409,
            )
        artifact = store.get(c, call["artifact_id"], "artifact")
        receipt = research.artifacts.read(artifact)
        response = receipt.get("response", {})
        choice = (response.get("choices") or [{}])[0]
        content = choice.get("message", {}).get("content")
        if (
            receipt.get("http_status") != 200
            or response.get("model") != call["model"]
            or choice.get("finish_reason") != "stop"
            or digest(receipt.get("request")) != call["request_hash"]
            or not isinstance(content, str)
            or not content.strip()
        ):
            raise DomainError(
                "The saved artifact has no verified complete matching reply", 409
            )
        chats = store.list(c, "chat", call["mission_id"])
        if len(chats) != 1:
            raise DomainError("A single matching council is required", 409)
        chat = chats[0]
        if (
            chat["provider"] != "nebius_token_factory"
            or chat.get("protocol", {}).get("version") != "reviewed_v3"
            or chat["status"] not in ("failed", "paused", "interrupted")
            or chat.get("active_turn")
            or c.execute(
                "SELECT 1 FROM jobs WHERE target_id=? AND state IN ('queued','running','waiting')",
                (chat["id"],),
            ).fetchone()
        ):
            raise DomainError(
                "The current council must be idle before local review recovery", 409
            )
        messages = council.messages(c, chat)
        turn = council.next_turn(chat, messages, c)
        if (
            not turn
            or turn["phase"]
            not in ("extraction", "scrutiny", "repair", "recheck", "synthesis")
            or f"chat:{chat['id']}:{turn['key']}" != call["purpose"]
            or turn["participant"]["model"] != call["model"]
            or not call.get("output_context_hash")
            or call["output_context_hash"]
            != council.output_recovery.context_hash(c, chat)
            or any(message.get("call_id") == call_id for message in messages)
        ):
            raise DomainError(
                "The saved review reply no longer matches the current unchanged council turn",
                409,
            )
        matching = [
            item
            for item in store.list(c, "call", call["mission_id"])
            if item.get("purpose") == call["purpose"]
        ]
        if not matching or matching[-1]["id"] != call_id:
            raise DomainError("A newer attempt supersedes this saved reply", 409)
        reservation = c.execute(
            "SELECT state FROM reservations WHERE id=? AND call_id=?",
            (call["reservation_id"], call_id),
        ).fetchone()
        if not reservation or reservation[0] != "settled":
            raise DomainError(
                "The original completed reservation must remain settled", 409
            )
        prompt, context_ids = council.prompt(chat, messages, turn, c)
        message_id = uid("message")
        from .review_delivery import admit_deliverable
        public = admit_deliverable(council, c, chat, turn, research.artifacts.redact(content), message_id)
        review_incomplete = bool(council.review.record(c, chat).get("delivery_degraded"))
        message = council.message(
            c,
            chat,
            id=message_id,
            role="assistant",
            content=public,
            phase=turn["phase"],
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
            context_hash=call["request_hash"],
            context_hash_kind="saved_provider_request",
            local_admission_prompt_hash=digest(prompt),
            call_id=call_id,
            source="model_api",
            provider=call["provider"],
            actual_model=call["model"],
            partial=review_incomplete,
            review_incomplete=review_incomplete,
            local_restoration_id=restoration_id,
        )
        chat.update(
            status="completed" if turn["phase"] == "synthesis" else "paused",
            active_turn=None,
            retry_wait=None,
            error=None,
            revision=chat["revision"] + 1,
        )
        if turn["phase"] == "synthesis":
            chat["final_message_id"] = message_id
        step = store.get(c, chat["step_id"], "step")
        step.update(
            paused=True,
            status="decision_ready" if turn["phase"] == "synthesis" else "committing",
        )
        store.put(c, "step", step)
        store.put(c, "chat", chat)
        result = {
            "chat_id": chat["id"],
            "call_id": call_id,
            "message_id": message["id"],
            "status": chat["status"],
            "new_inference_calls": 0,
            "financial_records_changed": False,
        }
        store.put(
            c,
            "review_reply_restoration",
            {
                "id": restoration_id,
                "mission_id": call["mission_id"],
                "policy": VERSION,
                "artifact_id": artifact["id"],
                "artifact_sha256": artifact["sha256"],
                "original_call_hash": digest(call),
                "origin": "trusted_operator_local_validation_recovery",
                "result": result,
                "created_at": now(),
            },
        )
        store.event(c, call["mission_id"], "review.saved_reply_restored", result)
        return result
