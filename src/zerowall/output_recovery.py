"""Explicit recovery from public drafts; provider-internal reasoning is not resumed."""

from copy import deepcopy

from .db import DomainError, digest
from .free_limits import CHAT_MAX_ATTEMPTS
from .usage import normalize


def join_draft(draft, continuation):
    if not draft:
        return continuation
    if continuation.startswith(draft):
        return continuation
    # Models sometimes repeat the unfinished sentence at the join.
    for overlap in range(min(len(draft), len(continuation), 4096), 7, -1):
        if draft.endswith(continuation[:overlap]):
            return draft + continuation[overlap:]
    return draft.rstrip() + "\n\n" + continuation.lstrip()


class OutputRecovery:
    def __init__(self, council):
        self.council, self.store, self.research = (
            council,
            council.store,
            council.research,
        )

    def context_hash(self, c, chat):
        review = (
            self.council.review.record(c, chat)
            if chat.get("mode") == "reviewed"
            else {}
        )
        return digest(
            {
                "protocol": chat["protocol_hash"],
                "generation": chat["generation"],
                "review_revision": review.get("revision"),
                "users": [
                    m["id"]
                    for m in self.council.messages(c, chat)
                    if m["role"] == "user"
                ],
                "sources": [
                    (s["id"], s.get("current_version_id"), s.get("removed", False))
                    for s in self.store.list(c, "source", chat["mission_id"])
                ],
            }
        )

    def artifact(self, c, call):
        return self.research.artifacts.read(
            self.store.get(c, call["artifact_id"], "artifact")
        )

    def draft(self, c, call, depth=0):
        if depth > CHAT_MAX_ATTEMPTS:
            raise DomainError("Saved output recovery chain exceeds its allowance", 409)
        text = (
            (self.artifact(c, call).get("response", {}).get("choices") or [{}])[0]
            .get("message", {})
            .get("content")
        )
        text = text if isinstance(text, str) else ""
        if call.get("recovery_mode") == "append_markdown":
            previous = self.store.get(c, call["recovery_from_call_id"], "call")
            if any(
                previous[key] != call[key] for key in ("mission_id", "purpose", "model")
            ):
                raise DomainError("Saved output does not belong to this turn", 409)
            text = join_draft(self.draft(c, previous, depth + 1), text)
        return self.research.artifacts.redact(text)

    def snapshot(self, c, chat):
        if chat["provider"] != "nebius_token_factory" or chat["status"] not in (
            "failed",
            "paused",
            "interrupted",
        ):
            return None
        turn = self.council.next_turn(chat, self.council.messages(c, chat), c)
        if not turn:
            return None
        purpose = f"chat:{chat['id']}:{turn['key']}"
        calls = [
            x
            for x in self.store.list(c, "call", chat["mission_id"])
            if x.get("purpose") == purpose
        ]
        if not calls:
            return None
        call = calls[-1]
        if (
            call.get("finish_reason") != "length"
            or call.get("http_status") != 200
            or call.get("actual_model") != turn["participant"]["model"]
        ):
            return None
        try:
            draft = self.draft(c, call)
        except (DomainError, OSError, ValueError):
            return None
        tokens = normalize(chat["provider"], call.get("usage"))["categories"]
        reason = None
        if call.get("output_context_hash") and call[
            "output_context_hash"
        ] != self.context_hash(c, chat):
            reason = "The question, sources or review changed. Resume normally to use the updated context."
        elif any(
            m["role"] == "user" and m["created_at"] > call["sent_at"]
            for m in self.council.messages(c, chat)
        ):
            reason = "New notes were added. Resume normally to include them."
        sources = self.store.list(c, "source", chat["mission_id"])
        if any(s.get("removed") for s in sources):
            reason = "A source was removed. Resume normally without reusing the old source context."
        elif not call.get("output_context_hash") and any(
            s["created_at"] > call["sent_at"] for s in sources
        ):
            reason = "Sources changed after this earlier attempt. Resume normally with the updated sources."
        try:
            self.research.budget.verification(c, call["model"])
            self.council.runtime.prepare_turn(c, chat, turn)
        except DomainError as error:
            reason = reason or error.message
        structured = chat.get("mode") == "reviewed" and turn["phase"] != "opening"
        capacity = self.research.provider.capacity(c, chat["mission_id"])
        budget = self.research.budget.summary(c, chat["mission_id"])
        mission = self.store.get(c, chat["mission_id"], "mission")
        allowance = self.research.council_preferences.allowance(c, chat)
        window = mission.get("direct_attempt_window", {})
        return {
            "attempts_used": capacity["attempts"] - window.get("start_attempt", 0),
            "attempt_limit": window.get("allowance", 20),
            "conversation_remaining_usd": allowance["remaining_usd"],
            "spending_scope": allowance["scope"],
            "limited_by_local_allowance": "remaining_existing_credit_allowance" in call.get("generation", {}).get("limiting_factors", []),
            "global_remaining_usd": budget["remaining_usd"],
            "generation": call.get("generation"),
            "call_id": call["id"],
            "model": call["model"],
            "name": turn["participant"]["name"],
            "phase": turn["phase"],
            "reasoning_tokens": tokens["output_reasoning"],
            "answer_tokens": tokens["output_visible"],
            "output_tokens": tokens["output_total_reported"],
            "partial_answer": draft[:16000],
            "preview_truncated": len(draft) > 16000,
            "has_saved_answer": bool(draft.strip()),
            "mode": "complete_stage" if structured else "append_markdown",
            "available": reason is None,
            "reason": reason,
            "action_label": "Complete saved response"
            if structured and draft.strip()
            else "Continue saved answer"
            if draft.strip()
            else "Answer now",
            "new_billed_request": True,
            "internal_reasoning_resumable": False,
        }

    def authorize(self, c, chat, call_id):
        value = self.snapshot(c, chat)
        if not value or value["call_id"] != call_id:
            raise DomainError(
                "This truncated attempt is no longer the current turn. Refresh the conversation.",
                409,
            )
        if not value["available"]:
            raise DomainError(value["reason"], 409)
        chat["pending_output_recovery"] = {
            "call_id": call_id,
            "context_hash": self.context_hash(c, chat),
            "mode": value["mode"],
            "authorized_revision": chat["revision"] + 1,
        }

    def prepare(self, c, mission_id, model, purpose, call_id, max_output):
        previous = self.store.get(c, call_id, "call")
        chats = self.store.list(c, "chat", mission_id)
        if (
            not chats
            or previous["mission_id"] != mission_id
            or previous["model"] != model
            or previous["purpose"] != purpose
            or previous.get("finish_reason") != "length"
        ):
            raise DomainError("Saved response does not match this council turn", 409)
        chat = chats[0]
        pending = chat.get("pending_output_recovery", {})
        if (
            pending.get("call_id") != call_id
            or pending.get("authorized_revision") != chat["revision"]
            or pending.get("context_hash") != self.context_hash(c, chat)
        ):
            raise DomainError(
                "Output recovery authorization is missing or obsolete. Refresh the conversation.",
                409,
            )
        saved = self.artifact(c, previous)
        request = deepcopy(saved["request"])
        if request.get("model") != model or not isinstance(
            request.get("messages"), list
        ):
            raise DomainError(
                "Saved request has no matching recoverable conversation", 409
            )
        request.update(max_completion_tokens=max_output, stream=False)
        request.pop("max_tokens", None)
        request.pop("tools", None)
        request.pop("tool_choice", None)
        # Replay public output only. Private reasoning is neither read nor requested.
        content = (
            (saved.get("response", {}).get("choices") or [{}])[0]
            .get("message", {})
            .get("content")
        )
        if isinstance(content, str) and content.strip():
            request["messages"].append({"role": "assistant", "content": content})
        instruction = "The previous attempt hit its output limit. Answer now: stop expanding the analysis and provide the final stage answer concisely. Do not expose private reasoning, request tools, repeat the problem or restart a long derivation. State essential assumptions and uncertainty; never invent missing evidence. "
        if pending["mode"] == "complete_stage":
            instruction += "Use the saved public draft as context. Return ONE COMPLETE response matching the original stage schema, including all required fields. Do not return a JSON fragment or research action."
        elif self.draft(c, previous).strip():
            instruction += "Continue the saved public answer from where it stopped. Return ONLY the remaining answer text; avoid repeating completed sections. You may repeat an unfinished final sentence to complete it. Finish the answer in this response."
        else:
            instruction += "No public answer text was saved. Return a complete concise answer to the original task. This is a new request, not a resumption of internal reasoning."
        request["messages"].append({"role": "user", "content": instruction})
        return request, {
            "recovery_from_call_id": call_id,
            "recovery_mode": pending["mode"],
            "recovery_rule": "answer_now",
            "internal_reasoning_resumed": False,
            "context_pack_id": previous.get("context_pack_id"),
            "chat_id": chat["id"],
            "authorization": pending,
        }

    def consume(self, c, recovery):
        chat = self.store.get(c, recovery["chat_id"], "chat")
        if (
            chat.get("pending_output_recovery") != recovery["authorization"]
            or chat["revision"] != recovery["authorization"]["authorized_revision"]
            or self.context_hash(c, chat) != recovery["authorization"]["context_hash"]
        ):
            raise DomainError(
                "The conversation changed before output recovery could start", 409
            )
        chat.pop("pending_output_recovery")
        self.store.put(c, "chat", chat)
