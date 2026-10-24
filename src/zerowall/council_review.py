"""Frozen-protocol dispatch; legacy histories never acquire new review semantics."""

from .council_review_v1 import CouncilReview as LegacyReview
from .db import DomainError, digest, now
from .contracts import ReviewOptions


class CouncilReview(LegacyReview):
    def next_turn(self, c, chat, messages):
        if chat.get("protocol", {}).get("version") == "reviewed_v4":
            return self.engine(chat).next_turn(c, chat, messages)
        return super().next_turn(c, chat, messages)

    def remaining(self, c, chat, messages):
        if chat.get("protocol", {}).get("version") == "reviewed_v4":
            return self.engine(chat).remaining(c, chat, messages)
        return super().remaining(c, chat, messages)

    def adoption_preview(self, c, chat):
        required = 2 * len(chat["participants"]) + 7
        result = {
            "available": chat["protocol"]["version"] != "reviewed_v4"
            and chat["status"] not in ("running", "waiting")
            and not chat.get("active_turn"),
            "allowed": True,
            "required_start": required,
            "reason": None,
            "display_name": "Council",
        }
        try:
            if chat["provider"] == "direct_council":
                self.research.direct_provider.validate(
                    c, [p["model"] for p in chat["participants"]], required=required
                )
            elif chat["provider"] == "openrouter_free":
                if not self.research.settings.openrouter_enabled:
                    raise DomainError(
                        "OpenRouter is disabled; the saved conversation remains available",
                        412,
                    )
                self.research.free_provider.capacity(
                    c, chat["mission_id"], required=required
                )
            elif chat["provider"] == "nebius_token_factory":
                for p in chat["participants"]:
                    effective = self.chat.runtime.effective_member(chat, p)
                    self.research.budget.verification(c, effective["model"])
        except DomainError as exc:
            result.update(allowed=False, reason=exc.message, code=exc.code)
        return result

    def adopt_scoped(self, c, chat, question, target="reviewed_v2", *, context_override=None, message_metadata=None):
        """A new governed cycle; old messages keep their original status."""
        if (
            chat.get("active_turn")
            or chat["status"] in ("running", "waiting")
            or c.execute(
                "SELECT COUNT(*) FROM jobs WHERE target_id=? AND state='running'",
                (chat["id"],),
            ).fetchone()[0]
        ):
            raise DomainError(
                "Pause and wait for the current request before starting the council review",
                409,
            )
        if (
            chat["provider"] == "openrouter_free"
            and not self.research.settings.openrouter_enabled
        ):
            raise DomainError(
                "OpenRouter is disabled; the saved conversation remains available", 412
            )
        preview = self.adoption_preview(c, chat)
        if not preview["allowed"]:
            raise DomainError(preview["reason"], preview.get("code", 429))
        previous = self.record(c, chat) if chat.get("review_id") else None
        previous_snapshot = self.snapshot(c, chat) if previous and target == "reviewed_v4" else None
        prior_answer = next((m for m in self.chat.messages(c, chat) if m["id"] == chat.get("final_message_id")), None)
        options = previous["contract"]["options"] if previous else ReviewOptions()
        combined = (
            (
                chat["original_prompt"]
                + "\n\nCurrent director request:\n"
                + question.strip()
            )
            if question.strip() != chat["original_prompt"]
            else question.strip()
        )
        if context_override is not None:
            combined = context_override["question"]
        if len(combined) > 8000 and context_override is None:
            raise DomainError(
                "The original question and follow-up exceed 8,000 characters. Shorten the follow-up before starting review in this chat.",
                422,
            )
        prior_cycle = max(
            (
                x.get("cycle", 0)
                for x in self.store.list(c, "chat_review", chat["mission_id"])
            ),
            default=0,
        )
        archive = {
            "protocol": chat["protocol"],
            "protocol_hash": chat["protocol_hash"],
            "mode": chat.get("mode", "discussion"),
            "review_id": chat.get("review_id"),
            "final_message_id": chat.get("final_message_id"),
            "accepted": chat.get("accepted", False),
            "last_message_sequence": len(self.chat.messages(c, chat)),
            "archived_at": now(),
        }
        chat.setdefault("protocol_history", []).append(archive)
        chat["protocol"] = {
            **chat["protocol"],
            "version": target,
            "mode": "reviewed",
            "initial_max_rounds": 1,
        }
        chat.update(
            mode="reviewed",
            protocol_hash=digest(chat["protocol"]),
            max_rounds=1,
            generation=chat.get("generation", 0) + 1,
            final_message_id=None,
            requested_finish=False,
            accepted=False,
            status="running",
            error=None,
            retry_wait=None,
            unavailable_members={},
            revision=chat["revision"] + 1,
        )
        if target == "reviewed_v4":
            chat["execution_descriptor"] = {**chat.get("execution_descriptor", {}), "version": "research/1", "parallel_openings": False,
                                            "delivery": "answer-delivery/1", "annotations": "answer-first/1"}
            chat["execution_descriptor_hash"] = digest(chat["execution_descriptor"])
        required = 2 * len(chat["participants"]) + 7
        self.chat.runtime.begin_window(c, chat, required, "explicit_council_adoption")
        if chat["provider"] == "openrouter_free":
            self.research.free_provider.capacity(
                c, chat["mission_id"], required=required
            )
        self.initialize(c, chat, options)
        record = self.record(c, chat)
        record.update(
            cycle=prior_cycle + 1,
            contract=self.contract(chat, combined, options, prior_cycle + 1),
        )
        record["contract_hash"] = digest(record["contract"])
        if previous:
            record["history"] = [
                *previous.get("history", []),
                {
                    "cycle": previous["cycle"],
                    "contract": previous["contract"],
                    "contract_hash": previous["contract_hash"],
                    "review_id": previous["id"],
                    "decision_hash": previous.get("published_decision_hash"),
                },
            ]
        if target == "reviewed_v4":
            record["conversation_checkpoint"] = {
                "version": "conversation-checkpoint/1", "source_cycle": previous["cycle"] if previous else 0,
                "prior_question": previous["contract"]["question"] if previous else chat["original_prompt"],
                "prior_answer": {"message_id": prior_answer["id"], "text": prior_answer["content"]} if prior_answer else None,
                "prior_assertions": (previous_snapshot or {}).get("claims", []),
                "prior_concerns": (previous_snapshot or {}).get("findings", []),
                "prior_assessments": (previous_snapshot or {}).get("rechecks", []),
                "rule": "Historical shared public context, not current-cycle evidence or a new successful check. Preserve original authors, limitations and dissent. Historical IDs cannot substitute for current source or claim IDs; unfinished current openings stay independent.",
            }
            record["conversation_checkpoint_hash"] = digest(record["conversation_checkpoint"])
        if context_override is not None:
            record["conversation_checkpoint"] = context_override["checkpoint"]
            record["conversation_checkpoint_hash"] = digest(record["conversation_checkpoint"])
        chat["review_cycle"] = record["cycle"]
        self.store.put(c, "chat_review", record)
        if target in ("reviewed_v3", "reviewed_v4"):
            self.engine(chat).prepare(c, chat)
        self.chat.message(
            c,
            chat,
            role="system",
            name="Council workflow",
            phase="protocol_transition",
            content="Council review starts here. Earlier answers keep their original review status. The council will propose independently, challenge material assertions, respond and revise, then check and synthesize the result.",
            review_cycle=record["cycle"],
            source="protocol_transition",
        )
        self.chat.message(
            c,
            chat,
            role="user",
            content=question.strip(),
            review_cycle=record["cycle"],
            **{"phase": "intervention", **(message_metadata or {})},
        )
        step = self.store.get(c, chat["step_id"], "step")
        step.update(paused=False, status="committing")
        self.store.put(c, "step", step)
        self.store.put(c, "chat", chat)
        c.execute(
            "UPDATE jobs SET state='cancelled' WHERE target_id=? AND state='queued'",
            (chat["id"],),
        )
        self.research.enqueue(c, "chat", chat)
        self.store.event(
            c,
            chat["mission_id"],
            "review.protocol_adopted",
            {
                "chat_id": chat["id"],
                "from_protocol_hash": archive["protocol_hash"],
                "to_protocol_hash": chat["protocol_hash"],
                "review_id": record["id"],
                "cycle": record["cycle"],
                "actor": "explicit_director_message",
            },
        )
        return self.chat.view(c, chat["id"])

    def new_cycle(self, c, chat, question, options=None, expected=None):
        if chat["protocol"]["version"] in ("reviewed_v3", "reviewed_v4"):
            return self.engine(chat).new_cycle(c, chat, question, options, expected)
        # Only execution allowance changes; prior publications and policy versions stay frozen.
        self.chat.runtime.begin_window(
            c, chat, 2 * len(chat["participants"]) + 7, "user_review_followup"
        )
        result = super().new_cycle(c, chat, question, options, expected)
        return result

    def engine(self, chat):
        version = chat.get("protocol", {}).get("version", "reviewed_v1")
        if version == "reviewed_v1":
            return None
        if version == "reviewed_v2":
            from .council_review_v2 import ScopedReview

            return ScopedReview(self.chat)
        if version == "reviewed_v4":
            from .council_review_v4 import AnswerFirstCouncil

            return AnswerFirstCouncil(self.chat)
        if version == "reviewed_v3":
            from .council_review_v3 import UnifiedCouncil

            return UnifiedCouncil(self.chat)
        raise DomainError(
            "Unknown review protocol; the saved chat was not reinterpreted", 422
        )

    def initialize(self, c, chat, options):
        if chat["protocol"]["version"] in ("reviewed_v3", "reviewed_v4"):
            return self.engine(chat).initialize(c, chat, options)
        return super().initialize(c, chat, options)

    def schedule(self, chat, record):
        if chat["protocol"]["version"] in ("reviewed_v3", "reviewed_v4"):
            return self.engine(chat).schedule(chat, record)
        return super().schedule(chat, record)

    def reassign(self, c, cid, body):
        result = super().reassign(c, cid, body)
        chat = result["chat"]
        if chat["protocol"]["version"] in ("reviewed_v3", "reviewed_v4"):
            self.engine(chat).save_plan(c, chat, self.record(c, chat))
            return self.chat.view(c, cid)
        return result

    def resynthesize(self, c, cid, expected):
        chat = self.store.get(c, cid, "chat")
        if chat["protocol"]["version"] in ("reviewed_v3", "reviewed_v4"):
            self.chat.runtime.begin_window(c, chat, 4, "explicit_updated_final")
        result = super().resynthesize(c, cid, expected)
        chat = result["chat"]
        if chat["protocol"]["version"] in ("reviewed_v3", "reviewed_v4"):
            record = self.record(c, chat)
            record["route"] = {
                "kind": "resynthesis",
                "reason": "Explicit update from current evidence and decisions",
            }
            self.engine(chat).save_plan(c, chat, record)
            return self.chat.view(c, cid)
        return result

    def contract(self, chat, question, options, revision):
        engine = self.engine(chat)
        return (
            engine.contract(chat, question, options, revision)
            if engine
            else super().contract(chat, question, options, revision)
        )

    def snapshot(self, c, chat):
        engine = self.engine(chat)
        return engine.snapshot(c, chat) if engine else super().snapshot(c, chat)

    def prompt(self, c, chat, messages, turn):
        engine = self.engine(chat)
        return (
            engine.prompt(c, chat, messages, turn)
            if engine
            else super().prompt(c, chat, messages, turn)
        )

    def _admit(self, c, chat, turn, content, message_id):
        engine = self.engine(chat)
        return (
            engine._admit(c, chat, turn, content, message_id)
            if engine
            else super()._admit(c, chat, turn, content, message_id)
        )

    def demo(self, c, chat, messages, turn):
        engine = self.engine(chat)
        return (
            engine.demo(c, chat, messages, turn)
            if engine
            else super().demo(c, chat, messages, turn)
        )

    def evidence(self, c, cid, body):
        chat = self.store.get(c, cid, "chat")
        engine = self.engine(chat)
        return (
            engine.evidence(c, cid, body) if engine else super().evidence(c, cid, body)
        )
