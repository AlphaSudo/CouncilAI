"""Independent public commits and idempotent annotation reconciliation.

Only public content reaches these records. Stream records contain no reasoning text.
No recovery method in this module calls a provider or changes a money row.
"""

import json
import sqlite3

from .db import DomainError, digest, now
from .review_delivery import admit_deliverable, public_text

VERSION = "answer-delivery/1"
TERMINAL = frozenset(("success", "partial", "degraded", "skipped"))


def enabled(chat):
    return chat.get("protocol", {}).get("version") == "reviewed_v4"


def stage_id(chat, turn):
    return "stage_" + digest([chat["id"], turn["key"]])[:28]


def stages(store, c, chat):
    return [
        r
        for r in store.list(c, "stage_result", chat["mission_id"])
        if r["chat_id"] == chat["id"]
    ]


def request_recovery(turn, call):
    """One unresolved physical attempt; only an explicit control may dispatch again."""
    return {
        "turn_key": turn["key"],
        "call_id": call["id"],
        "phase": turn["phase"],
        "member_id": turn["participant"]["id"],
        "model": turn["participant"]["model"],
        "name": turn["participant"]["name"],
        "error": call.get("error"),
        "unknown_charge_retained": True,
    }


class AnswerDelivery:
    def __init__(self, chat):
        self.chat, self.store, self.research = chat, chat.store, chat.research

    def commit(
        self,
        cid,
        turn,
        content,
        call,
        prompt,
        context_ids,
        input_revision,
        *,
        state="complete",
    ):
        """Commit public message and receipt reference before entering the sidecar transaction."""
        content = self.research.artifacts.redact(content)
        delivery_id = (
            "delivery_"
            + digest([cid, turn["key"], call["id"] if call else "fixture"])[:28]
        )
        with self.store.tx() as c:
            existing = c.execute(
                "SELECT body FROM records WHERE id=?", (delivery_id,)
            ).fetchone()
            if existing:
                return json.loads(existing[0])
            chat = self.store.get(c, cid, "chat")
            messages = self.chat.messages(c, chat)
            explanation_only = (
                self.chat.review.record(c, chat).get("route", {}).get("kind")
                == "explain"
            )
            readable = (
                content
                if turn["phase"] == "opening"
                else public_text(content, turn["phase"])
            )
            message = self.chat.message(
                c,
                chat,
                role="assistant",
                content=readable,
                defer_annotations=True,
                phase=turn["phase"],
                round=turn["round"],
                participant_id=turn["participant"]["id"],
                name=turn["participant"]["name"],
                model=turn["participant"]["model"],
                actual_model=(call or {}).get(
                    "actual_model",
                    turn["participant"].get(
                        "actual_model", turn["participant"]["model"]
                    ),
                ),
                provider=turn["participant"].get("provider", chat["provider"]),
                turn_key=turn["key"],
                review_cycle=turn.get("cycle"),
                call_id=(call or {}).get("id"),
                **({"web_search": call["web_search"]} if call and call.get("web_search") else {}),
                generation_state=state,
                review_state="pending",
                support_state="unassessed",
                raw_public_hash=digest(content),
                content_hash=digest(readable),
                public_answer=turn["phase"] in ("opening", "repair", "synthesis"),
                explanation_only=explanation_only,
                context_hash=digest(prompt),
                context_message_ids=context_ids,
                seen_user_sequence=max(
                    (
                        m["sequence"]
                        for m in messages
                        if m["role"] == "user" and m["id"] in context_ids
                    ),
                    default=0,
                ),
                source="model_api" if call else "fixture",
                ready=False,
                outdated_context=False,
                partial=state != "complete",
                review_incomplete=False,
                replacement_for=turn["participant"].get("replacement_for"),
                replacement_name=turn["participant"].get("replacement_name"),
            )
            item = {
                "id": delivery_id,
                "mission_id": chat["mission_id"],
                "chat_id": cid,
                "version": VERSION,
                "turn": turn,
                "message_id": message["id"],
                "call_id": (call or {}).get("id"),
                "artifact_id": (call or {}).get("artifact_id"),
                "request_hash": (call or {}).get("request_hash"),
                "raw_public_content": content,
                "raw_public_hash": digest(content),
                "context_hash": digest(prompt),
                "input_revision": input_revision,
                "state": "pending",
                "saved_chat_status": chat["status"],
                "generation_state": state,
            }
            self.store.put(c, "answer_delivery", item)
            self.store.put(
                c,
                "stage_result",
                {
                    "id": stage_id(chat, turn),
                    "mission_id": chat["mission_id"],
                    "chat_id": cid,
                    "review_cycle": turn.get("cycle"),
                    "turn_key": turn["key"],
                    "phase": turn["phase"],
                    "state": "pending",
                    "generation_state": state,
                    "review_state": "pending",
                    "context_hash": digest(prompt),
                    "call_id": item["call_id"],
                    "message_id": message["id"],
                    "receipt_id": item["artifact_id"],
                    "warning_ids": [],
                    "annotation_coverage": "unknown",
                },
            )
            chat.update(
                generation_state="complete"
                if turn["phase"] == "synthesis"
                else "responding",
                review_state="pending",
            )
            self.store.put(c, "chat", chat)
            self.store.event(
                c,
                chat["mission_id"],
                "chat.public_answer_saved",
                {"chat_id": cid, "message_id": message["id"]},
            )
            return item

    def annotate(self, delivery_id, *, recovering=False):
        with self.store.tx() as c:
            item = self.store.get(c, delivery_id, "answer_delivery")
            if item["state"] == "done":
                return item
            chat = self.store.get(c, item["chat_id"], "chat")
            turn = item["turn"]
            # Governed context must still match; stale text remains public but cannot grant current links.
            if chat.get("review_cycle") != turn.get("cycle"):
                raise DomainError(
                    "Saved public reply belongs to a historical cycle", 409
                )
            if digest(item["raw_public_content"]) != item["raw_public_hash"]:
                raise DomainError("Saved public reply integrity changed", 422)
            if item["call_id"]:
                call = self.store.get(c, item["call_id"], "call")
                if (
                    call.get("artifact_id") != item["artifact_id"]
                    or call.get("request_hash") != item["request_hash"]
                ):
                    raise DomainError("Saved public receipt changed", 422)
            if (
                recovering
                and chat["status"] == "interrupted"
                and item["saved_chat_status"] == "running"
            ):
                chat["status"] = "running"
            record = self.chat.review.record(c, chat)
            outdated = record["revision"] != item["input_revision"]
            rendered = admit_deliverable(
                self.chat, c, chat, turn, item["raw_public_content"], item["message_id"]
            )
            record = self.chat.review.record(c, chat)
            incomplete = bool(
                record.get("delivery_degraded")
                or chat.get("requested_finish")
                or chat.get("unavailable_members")
            )
            message = self.store.get(c, item["message_id"], "chat_message")
            # Every committed public reply is immutable, including structured
            # review notes. Annotation may append status, never replace the
            # author's output with a shorter ledger/summary.
            if not message["content"]:
                message["content"] = rendered
                message["content_hash"] = digest(rendered)
            message.update(
                review_state="incomplete" if incomplete else "complete",
                review_incomplete=incomplete,
                partial=message.get("partial", False) or incomplete,
                outdated_context=outdated,
            )
            c.execute("SAVEPOINT citation_sidecar")
            try:
                message["research_citations"] = self.research.library.bind_message(
                    c, chat, message
                )
                self.research.library.rechecked(c, chat, message)
                c.execute("RELEASE citation_sidecar")
            except (sqlite3.Error, OSError, MemoryError):
                c.execute("ROLLBACK TO citation_sidecar")
                c.execute("RELEASE citation_sidecar")
                raise
            except Exception:  # noqa: BLE001 - isolate citation sidecar bugs after the public commit
                c.execute("ROLLBACK TO citation_sidecar")
                c.execute("RELEASE citation_sidecar")
                incomplete = True
                record.update(delivery_degraded=True)
                message.update(review_state="incomplete", review_incomplete=True)
                message.pop("research_citations", None)
                self.store.put(c, "chat_review", record)
                self.chat.review.engine(chat).put(
                    c,
                    chat,
                    record,
                    "review_warning",
                    {
                        "category": "sidecar_unavailable",
                        "source_message_id": message["id"],
                        "path": ["research_citations"],
                        "consequence": "Citation interpretation unavailable; source text remains saved",
                        "public_note": "Some review details are unavailable",
                        "grants_authority": False,
                    },
                )
            self.store.put(c, "chat_message", message)
            if outdated:
                record.update(stale=True, synthesis_stale=True)
                self.store.put(c, "chat_review", record)
            warning_ids = [
                w["id"]
                for w in self.store.list(c, "review_warning", chat["mission_id"])
                if w.get("source_message_id") == message["id"]
            ]
            stage = self.store.get(c, stage_id(chat, turn), "stage_result")
            warnings = [
                w
                for w in record.get("delivery_warnings", [])
                if w.get("source_message_id") == message["id"]
            ]
            stage.update(
                state="degraded"
                if warnings and not rendered.strip()
                else "partial"
                if warnings or incomplete
                else "success",
                review_state=message["review_state"],
                warning_ids=warning_ids,
                annotation_coverage="partial" if warnings or incomplete else "assessed",
                completed_at=now(),
            )
            if warnings and not any(
                r.get("source_message_id") == message["id"]
                for r in self.store.list(c, "review_admission", chat["mission_id"])
                if r.get("origin") == "record_level_admission"
            ):
                stage["state"] = "degraded"
            self.store.put(c, "stage_result", stage)
            for planned in self.chat.review.schedule(chat, record):
                if (
                    planned["key"] in record.get("skipped_keys", [])
                    and not c.execute(
                        "SELECT 1 FROM records WHERE id=?", (stage_id(chat, planned),)
                    ).fetchone()
                ):
                    self.store.put(
                        c,
                        "stage_result",
                        {
                            "id": stage_id(chat, planned),
                            "mission_id": chat["mission_id"],
                            "chat_id": chat["id"],
                            "review_cycle": planned.get("cycle"),
                            "turn_key": planned["key"],
                            "phase": planned["phase"],
                            "state": "skipped",
                            "generation_state": "not_requested",
                            "review_state": "unavailable",
                            "annotation_coverage": "none",
                            "warning_ids": [],
                            "reason": "Unavailable prerequisite annotations; proceed to synthesis",
                        },
                    )
            chat.update(
                active_turn=None,
                error=None,
                retry_wait=None,
                revision=chat["revision"] + 1,
                review_state="incomplete" if incomplete else "complete",
            )
            if chat.get("pending_request_recovery", {}).get("turn_key") == turn["key"]:
                chat.pop("pending_request_recovery", None)
            if turn["phase"] == "synthesis":
                chat.update(
                    final_message_id=message["id"],
                    generation_state=item["generation_state"],
                )
                from .answer_budget import release

                release(self.chat, c, chat)
            item.update(state="done", annotated_at=now())
            self.store.put(c, "answer_delivery", item)
            if chat["status"] == "running":
                if self.chat.next_turn(chat, self.chat.messages(c, chat), c):
                    self.research.enqueue(c, "chat", chat)
                else:
                    chat["status"] = "completed"
                    self.chat.runtime.release_capacity(
                        c, chat["mission_id"], "Completed"
                    )
                    step = self.store.get(c, chat["step_id"], "step")
                    step["status"] = "decision_ready"
                    self.store.put(c, "step", step)
            self.store.put(c, "chat", chat)
            self.apply_steering(c, chat)
            self.store.event(
                c,
                chat["mission_id"],
                "chat.turn_completed",
                {
                    "chat_id": chat["id"],
                    "message_id": message["id"],
                    "status": chat["status"],
                },
            )
            return item

    def reconcile(self, cid=None):
        """Only local pending commits; safe to repeat after every restart."""
        with self.store.tx() as c:
            pending = [
                json.loads(row[0])
                for row in c.execute(
                    "SELECT body FROM records WHERE kind='answer_delivery'"
                )
                if json.loads(row[0]).get("state") == "pending"
            ]
        count = self.reconcile_receipts(cid)
        for item in pending:
            if cid and item["chat_id"] != cid:
                continue
            self.annotate(item["id"], recovering=True)
            count += 1
        return count

    def reconcile_receipts(self, cid=None):
        """Close the receipt-to-message crash interval, with exact saved dispatch bindings."""
        ready = []
        with self.store.tx() as c:
            intents = [
                json.loads(row[0])
                for row in c.execute(
                    "SELECT body FROM records WHERE kind='answer_intent'"
                )
            ]
            for intent in intents:
                if cid and cid != intent["chat_id"]:
                    continue
                chat = self.store.get(c, intent["chat_id"], "chat")
                if not enabled(chat) or chat.get("review_cycle") != intent["turn"].get(
                    "cycle"
                ):
                    continue
                if any(
                    m.get("turn_key") == intent["turn"]["key"]
                    for m in self.chat.messages(c, chat)
                ):
                    continue
                calls = [
                    call
                    for call in self.store.list(c, "call", chat["mission_id"])
                    if call.get("answer_intent_id") == intent["id"]
                ]
                if not calls:
                    continue
                call = calls[-1]
                if (
                    call.get("state") != "completed"
                    or call.get("finish_reason") != "stop"
                    or call.get("actual_model")
                    != intent["turn"]["participant"]["model"]
                    or call.get("answer_intent_hash") != digest(intent)
                    or chat.get("protocol_hash") != intent["protocol_hash"]
                    or call.get("output_context_hash")
                    != self.chat.output_recovery.context_hash(c, chat)
                ):
                    continue
                money = c.execute(
                    "SELECT state FROM reservations WHERE id=? AND call_id=?",
                    (call["reservation_id"], call["id"]),
                ).fetchone()
                if not money or money[0] != "settled":
                    continue
                receipt = self.research.artifacts.read(
                    self.store.get(c, call["artifact_id"], "artifact")
                )
                response = receipt.get("response", {})
                choice = (response.get("choices") or [{}])[0]
                text = choice.get("message", {}).get("content")
                if (
                    digest(receipt.get("request")) != call["request_hash"]
                    or response.get("model") != call["model"]
                    or not isinstance(text, str)
                    or not text.strip()
                ):
                    continue
                ready.append((intent, call, text))
        for intent, call, text in ready:
            item = self.commit(
                intent["chat_id"],
                intent["turn"],
                text,
                call,
                intent["prompt"],
                intent["context_ids"],
                intent["input_revision"],
            )
            # Store.recover has already moved a previously running chat to interrupted.
            with self.store.tx() as c:
                item["saved_chat_status"] = intent["saved_chat_status"]
                self.store.put(c, "answer_delivery", item)
            self.annotate(item["id"], recovering=True)
        self.reopen_empty_unknown_boundaries(cid)
        return len(ready)

    def reopen_empty_unknown_boundaries(self, cid=None):
        """Locally recover the earlier empty-final bug, without dispatch or settlement."""
        restored = 0
        with self.store.tx() as c:
            rows = c.execute("SELECT body FROM records WHERE kind='chat'").fetchall()
            for row in rows:
                chat = json.loads(row[0])
                if cid and chat["id"] != cid:
                    continue
                if (
                    not enabled(chat)
                    or chat.get("status") != "completed"
                    or chat.get("accepted")
                    or chat.get("requested_finish")
                ):
                    continue
                if (
                    chat.get("completion_reason") != "provider_or_action_boundary"
                    or chat.get("generation_state") != "unavailable"
                ):
                    continue
                if c.execute(
                    "SELECT 1 FROM jobs WHERE target_id=? AND state IN ('queued','running')",
                    (chat["id"],),
                ).fetchone():
                    continue
                messages = self.chat.messages(c, chat)
                notice = next(
                    (m for m in messages if m["id"] == chat.get("final_message_id")),
                    None,
                )
                if (
                    not notice
                    or notice.get("source") != "local_partial"
                    or any(
                        m["role"] == "assistant"
                        and m.get("review_cycle") == chat.get("review_cycle")
                        for m in messages
                    )
                ):
                    continue
                record = self.chat.review.record(c, chat)
                turns = {t["key"]: t for t in self.chat.review.schedule(chat, record)}
                calls = [
                    call
                    for call in self.store.list(c, "call", chat["mission_id"])
                    if call.get("purpose", "").removeprefix(f"chat:{chat['id']}:")
                    in turns
                ]
                if not calls:
                    continue
                call = max(
                    calls,
                    key=lambda item: item.get("sent_at", item.get("created_at", "")),
                )
                if call["state"] != "unknown":
                    continue
                turn = turns[call["purpose"].removeprefix(f"chat:{chat['id']}:")]
                chat.update(
                    status="paused",
                    final_message_id=None,
                    active_turn=None,
                    error="The provider connection was interrupted. Retry this response or explicitly continue with the other models; the earlier possible charge remains counted.",
                    pending_request_recovery=request_recovery(turn, call),
                    revision=chat["revision"] + 1,
                )
                chat.pop("completion_reason", None)
                step = self.store.get(c, chat["step_id"], "step")
                step["paused"] = True
                self.store.put(c, "step", step)
                self.store.put(c, "chat", chat)
                self.store.event(
                    c,
                    chat["mission_id"],
                    "chat.unknown_request_reopened",
                    {
                        "chat_id": chat["id"],
                        "call_id": call["id"],
                        "turn_key": turn["key"],
                        "preserved_notice_id": notice["id"],
                        "provider_dispatched": False,
                        "financial_rows_changed": False,
                    },
                )
                restored += 1
        return restored

    def failed_turn(self, job, error):
        """A failed seat is not a failed conversation. Never replay an ambiguous request."""
        if isinstance(error, (sqlite3.Error, OSError, MemoryError)):
            return False
        with self.store.tx() as c:
            chat = self.store.get(c, job["target_id"], "chat")
            if not enabled(chat):
                return False
            turn = self.chat.next_turn(chat, self.chat.messages(c, chat), c)
            if not turn:
                return False
            # Integrity and authorization errors may block dispatch; do not bless them as review faults.
            code = error.code if isinstance(error, DomainError) else None
            if code in (409, 422):
                return False  # Frozen protocol/revision/storage integrity is an actual action boundary.
            calls = [
                call
                for call in self.store.list(c, "call", chat["mission_id"])
                if call.get("purpose") == f"chat:{chat['id']}:{turn['key']}"
            ]
            call = calls[-1] if calls else None
            partial = ""
            if call and call.get("artifact_id"):
                receipt = self.research.artifacts.read(
                    self.store.get(c, call["artifact_id"], "artifact")
                )
                partial = (receipt.get("response", {}).get("choices") or [{}])[0].get(
                    "message", {}
                ).get("content") or ""
            if not partial and call:
                stream = c.execute(
                    "SELECT body FROM records WHERE id=?",
                    ("public_stream_" + call["id"],),
                ).fetchone()
                if stream:
                    partial = "".join(
                        chunk["text"] for chunk in json.loads(stream[0])["chunks"]
                    )
            content = (
                partial
                if turn["phase"] == "opening"
                else public_text(partial, turn["phase"])
            )
            if content:
                self.chat.message(
                    c,
                    chat,
                    role="assistant",
                    content=self.research.artifacts.redact(content),
                    phase=turn["phase"],
                    round=turn["round"],
                    turn_key=turn["key"],
                    review_cycle=turn.get("cycle"),
                    participant_id=turn["participant"]["id"],
                    model=turn["participant"]["model"],
                    name=turn["participant"]["name"],
                    actual_model=(call or {}).get("actual_model") or "unknown",
                    provider=(call or {}).get("provider", chat["provider"]),
                    call_id=(call or {}).get("id"),
                    source="model_api",
                    generation_state="partial",
                    review_state="unavailable",
                    partial=True,
                    defer_annotations=True,
                )
            reason = self.research.artifacts.redact(
                error.message
                if isinstance(error, DomainError)
                else "The provider could not complete this step"
            )
            self.store.put(
                c,
                "stage_result",
                {
                    "id": stage_id(chat, turn),
                    "mission_id": chat["mission_id"],
                    "chat_id": chat["id"],
                    "review_cycle": turn.get("cycle"),
                    "turn_key": turn["key"],
                    "phase": turn["phase"],
                    "state": "partial" if content else "degraded",
                    "generation_state": "partial" if content else "unavailable",
                    "review_state": "unavailable",
                    "reason": reason,
                    "call_id": (call or {}).get("id"),
                    "warning_ids": [],
                },
            )
            record = self.chat.review.record(c, chat)
            record["delivery_degraded"] = True
            record.setdefault("delivery_warnings", []).append(
                {"phase": turn["phase"], "reason": reason}
            )
            if (
                turn["phase"] in ("extraction", "scrutiny")
                and (call or {}).get("state") != "unknown"
            ):
                record["skipped_keys"] = list(
                    set(record.get("skipped_keys", []))
                    | {
                        t["key"]
                        for t in self.chat.review.schedule(chat, record)
                        if t["phase"] not in ("opening", "synthesis")
                    }
                )
            self.store.put(c, "chat_review", record)
            self.chat.review.engine(chat).save_plan(c, chat, record)
            chat.update(
                active_turn=None,
                retry_wait=None,
                error=None,
                review_state="incomplete",
                revision=chat["revision"] + 1,
            )
            boundary = (
                code in (401, 402, 403, 409, 412, 422, 429)
                or (call or {}).get("state") == "unknown"
            )
            held_final = c.execute(
                "SELECT 1 FROM reservations WHERE mission_id=? AND state='held'",
                (chat["mission_id"],),
            ).fetchone()
            finish_instead = (
                code in (402, 429)
                and turn["phase"] not in ("opening", "synthesis")
                and held_final
                and (call or {}).get("state") != "unknown"
            )
            if (call or {}).get("state") == "unknown" and chat["status"] != "cancelled":
                # A transport failure is not a completed answer or a user refusal.
                # Keep the failed logical turn available, but never enqueue it here.
                chat.update(
                    status="paused",
                    error=reason,
                    pending_request_recovery=request_recovery(turn, call),
                    generation_state="partial" if content else "unavailable",
                )
                chat.pop("completion_reason", None)
                step = self.store.get(c, chat["step_id"], "step")
                step["paused"] = True
                self.store.put(c, "step", step)
            elif chat["status"] in ("paused", "cancelled"):
                pass  # Explicit user control is never converted into automatic synthesis or completion.
            elif finish_instead and chat["status"] == "running":
                chat["requested_finish"] = True
                self.research.enqueue(c, "chat", chat)
            elif turn["phase"] == "synthesis" or boundary:
                answers = [
                    m
                    for m in self.chat.messages(c, chat)
                    if m.get("role") == "assistant"
                    and m.get("review_cycle") == chat.get("review_cycle")
                    and m.get("content")
                ]
                rendered = (
                    "A complete council conclusion is unavailable. " + reason + "\n\n"
                )
                rendered += "\n\n".join(
                    "### "
                    + m.get("name", "Participant")
                    + " — saved response\n\n"
                    + m["content"]
                    for m in answers
                )
                if not answers:
                    rendered += "No public model answer was received. The question and attempted requests are saved."
                final = self.chat.message(
                    c,
                    chat,
                    role="system",
                    name="Saved council responses",
                    phase="synthesis",
                    round=turn["round"],
                    review_cycle=turn.get("cycle"),
                    content=rendered,
                    source="local_partial",
                    generation_state="partial" if answers else "unavailable",
                    review_state="incomplete",
                    partial=True,
                    review_incomplete=True,
                )
                chat.update(
                    status="completed",
                    final_message_id=final["id"],
                    generation_state=final["generation_state"],
                    completion_reason="provider_or_action_boundary",
                )
                from .answer_budget import release

                release(self.chat, c, chat)
            elif chat["status"] == "running":
                self.research.enqueue(c, "chat", chat)
            self.store.put(c, "chat", chat)
            c.execute("UPDATE jobs SET state='completed' WHERE id=?", (job["id"],))
            return True

    def apply_steering(self, c, chat):
        queued = [
            x
            for x in self.store.list(c, "chat_steering", chat["mission_id"])
            if x["state"] == "queued"
        ]
        if not queued or chat["status"] in ("cancelled", "paused"):
            return
        next_turn = self.chat.next_turn(chat, self.chat.messages(c, chat), c)
        # Preserve the same question/evidence for all unfinished independent openings.
        if next_turn and next_turn["phase"] == "opening":
            return
        text = "\n\n".join(x["text"] for x in queued)
        if chat["status"] == "completed":
            self.chat.review.new_cycle(c, chat, text)
        else:
            self.chat.message(
                c,
                chat,
                role="user",
                content=text,
                phase="intervention",
                review_cycle=chat.get("review_cycle"),
                source="queued_director_steering",
            )
            chat["revision"] += 1
            self.store.put(c, "chat", chat)
        for item in queued:
            item.update(
                state="applied",
                applied_at=now(),
                applied_cycle=chat.get("review_cycle"),
            )
            self.store.put(c, "chat_steering", item)


def save_stream(store, artifacts, c, call, parts, *, complete=False):
    """A replayable public prefix. Hold any suffix which may be part of a secret.

    Redact the entire prefix before slicing. This prevents leaking a complete key
    straddling the previous flush boundary, and never changes already emitted text.
    """
    if not call.get("purpose", "").startswith("chat:"):
        return
    text = "".join(parts)
    # Hold only a suffix matching the prefix of an actual secret, plus a CR for stable line endings.
    withheld = 0
    if not complete:
        for secret in artifacts.secrets:
            for size in range(1, min(len(secret), len(text)) + 1):
                if text.endswith(secret[:size]):
                    withheld = max(withheld, size)
        if text.endswith("\r"):
            withheld = max(withheld, 1)
    safe = artifacts.redact(text[:-withheld] if withheld else text)
    stream_id = "public_stream_" + call["id"]
    row = c.execute("SELECT body FROM records WHERE id=?", (stream_id,)).fetchone()
    previous = (
        json.loads(row[0])
        if row
        else {
            "id": stream_id,
            "mission_id": call["mission_id"],
            "call_id": call["id"],
            "model": call["model"],
            "purpose": call["purpose"],
            "chunks": [],
            "length": 0,
        }
    )
    if previous["length"] > len(safe) or digest(
        safe[: previous["length"]]
    ) != previous.get("prefix_hash", digest("")):
        raise DomainError("Public stream prefix changed", 422)
    delta = safe[previous["length"] :]
    if not delta and previous.get("complete") == complete:
        return
    # Bounded writes: flush once per progress tick; every chunk <= 16 KiB of characters.
    for start in range(0, len(delta), 16384):
        previous["chunks"].append(
            {"seq": len(previous["chunks"]) + 1, "text": delta[start : start + 16384]}
        )
    previous.update(
        length=len(safe), prefix_hash=digest(safe), complete=complete, updated_at=now()
    )
    store.put(c, "public_stream", previous)
