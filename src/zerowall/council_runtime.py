"""Execution allowances and disclosed model substitutions, separate from review policy."""

import json
from datetime import UTC, datetime

from .db import DomainError, now, uid
from .free_limits import CHAT_MAX_ATTEMPTS, RETRY_ALLOWANCE


class CouncilRuntime:
    def __init__(self, chat):
        self.chat = chat
        self.research = chat.research
        self.store = chat.store

    def begin_window(self, c, chat, required, reason):
        if chat["provider"] not in ("direct_council", "nebius_token_factory"):
            return
        if 'next_research_enabled' in chat:
            chat['research_enabled'] = chat.pop('next_research_enabled')
        if chat.get('research_enabled') and 'collective_research_enabled' not in chat and chat.get('mode') == 'reviewed' and chat.get('protocol', {}).get('version') in ('reviewed_v3', 'reviewed_v4'):
            chat['collective_research_enabled'] = True
            self.store.event(c, chat['mission_id'], 'research.collective_adopted', {'chat_id': chat['id'], 'applies_to': 'new_explicit_request', 'original_messages_unchanged': True})
        chat['research_tools_enabled'] = bool(chat.get('research_tools_enabled') or chat.get('research_enabled') or self.store.list(c, 'source', chat['mission_id']))
        if not chat.get('execution_descriptor'):
            from .db import digest
            chat['execution_descriptor'] = {'version': 'research/1', 'accounting': 'usage/1', 'source_policy': 'scoped/1', 'parallel_openings': False}
            chat['execution_descriptor_hash'] = digest(chat['execution_descriptor'])
            self.store.event(c, chat['mission_id'], 'chat.execution_adopted', {'applies_to': 'new_explicit_request', 'original_messages_unchanged': True})
        if chat.get('research_tools_enabled') and reason not in ('initial_request', 'explicit_explanation', 'explicit_updated_final'):
            required = min(20, required + 5)
        # Preflight a new bounded request, not the exhausted previous request.
        if chat['provider'] == 'direct_council':
            self.research.direct_provider.validate(c, [p['model'] for p in chat['participants']], chat['mission_id'], required=required, fresh_window=True)
        else:
            for participant in chat['participants']:
                effective = self.effective_member(chat, participant) if chat.get('protocol', {}).get('version') == 'reviewed_v4' else participant
                self.research.budget.verification(c, effective['model'])
            self.research.provider.capacity(c, chat['mission_id'], required=required, fresh_window=True)
        mission = self.store.get(c, chat["mission_id"], "mission")
        total = len(
            [
                x
                for x in self.store.list(c, "call", chat["mission_id"])
                if x.get("accounting_provider", x.get("provider")) == chat["provider"]
            ]
        )
        grant = {
            "id": uid("allowance"),
            "mission_id": chat["mission_id"],
            "chat_id": chat["id"],
            "start_attempt": total,
            "allowance": CHAT_MAX_ATTEMPTS,
            "required": required,
            "reason": reason,
            "research_call_limit": 5 if chat.get('research_tools_enabled') and reason not in ('explicit_explanation', 'explicit_updated_final') else 0,
            "research_enabled": bool(chat.get('research_enabled')),
            "execution_descriptor_hash": chat.get('execution_descriptor_hash'),
            "created_at": now(),
        }
        mission["direct_attempt_window"] = grant
        chat["retry_window_start"] = chat.get("retry_used", 0)
        self.store.put(c, "mission", mission)
        self.store.put(c, "chat_allowance", grant)
        self.store.event(c, chat["mission_id"], "chat.allowance_opened", grant)
        if chat["provider"] == "direct_council" and chat["protocol"]["version"] in ("reviewed_v3", "reviewed_v4"):
            self.release_capacity(c, chat["mission_id"], "New explicit request window")
            self.reserve_capacity(c, chat, required)

    def reserve_capacity(self, c, chat, required):
        self.research.direct_provider.capacity(c, chat["mission_id"], required=required)
        lease = {
            "id": uid("capacity"),
            "mission_id": chat["mission_id"],
            "chat_id": chat["id"],
            "day": datetime.now(UTC).date().isoformat(),
            "remaining": required,
            "initial": required,
            "state": "active",
            "created_at": now(),
        }
        self.store.put(c, "chat_capacity", lease)
        self.store.event(c, chat["mission_id"], "chat.capacity_reserved", lease)

    def consume_capacity(self, c, mission_id):
        today = datetime.now(UTC).date().isoformat()
        leases = [
            x
            for x in self.store.list(c, "chat_capacity", mission_id)
            if x["state"] == "active" and x["day"] == today
        ]
        for lease in leases:
            if lease["remaining"]:
                lease["remaining"] -= 1
                self.store.put(c, "chat_capacity", lease)
                return

    def release_capacity(self, c, mission_id, reason):
        for lease in self.store.list(c, "chat_capacity", mission_id):
            if lease["state"] == "active":
                unused = lease["remaining"]
                lease.update(
                    state="released",
                    remaining=0,
                    released_at=now(),
                    reason=reason,
                    unused=unused,
                )
                self.store.put(c, "chat_capacity", lease)
                self.store.event(
                    c,
                    mission_id,
                    "chat.capacity_released",
                    {"lease_id": lease["id"], "unused": unused, "reason": reason},
                )

    def expand(self, c, chat, extra):
        """Reserve one optional exchange while preserving the final and reserve."""
        if chat["provider"] != "direct_council":
            return
        lease = next(
            (
                x
                for x in reversed(
                    self.store.list(c, "chat_capacity", chat["mission_id"])
                )
                if x["state"] == "active"
                and x["day"] == datetime.now(UTC).date().isoformat()
            ),
            None,
        )
        if not lease:
            raise DomainError(
                "No current daily reservation remains for another exchange", 429
            )
        if lease['initial'] + extra > 20 and chat.get('research_tools_enabled'):
            mission = self.store.get(c, chat['mission_id'], 'mission')
            window = mission['direct_attempt_window']
            admitted = sum(x['amount'] for x in self.store.list(c, 'resource_reservation', chat['mission_id']) if x['kind'] == 'research_calls' and x['scope'] == window['id'] and x['state'] != 'released')
            limit = window.get('research_call_limit', 5)
            if limit - admitted >= extra:
                window['research_call_limit'] = limit - extra
                self.store.put(c, 'mission', mission)
                self.store.event(c, chat['mission_id'], 'chat.research_reallocated', {'extra_base_calls': extra, 'remaining_research_limit': window['research_call_limit'], 'attempt_ceiling': 20})
                return
        required = lease["remaining"] + extra
        self.research.direct_provider.capacity(c, chat["mission_id"], required=required)
        if lease["initial"] + extra > 20:
            raise DomainError(
                "The focused exchange exceeds this request's attempt ceiling", 429
            )
        lease.update(remaining=required, initial=lease["initial"] + extra)
        self.store.put(c, "chat_capacity", lease)
        self.store.event(
            c,
            chat["mission_id"],
            "chat.capacity_expanded",
            {"lease_id": lease["id"], "extra": extra},
        )

    def reserved_remaining(self, c, chat):
        return sum(
            x["remaining"]
            for x in self.store.list(c, "chat_capacity", chat["mission_id"])
            if x["state"] == "active"
            and x["day"] == datetime.now(UTC).date().isoformat()
        )

    def recovery_usage(self, c, chat):
        mission = self.store.get(c, chat["mission_id"], "mission")
        start = mission.get("direct_attempt_window", {}).get("start_attempt", 0)
        calls = [
            x
            for x in self.store.list(c, "call", chat["mission_id"])
            if x.get("accounting_provider", x.get("provider")) == chat["provider"]
        ][start:]
        groups = {}
        for call in calls:
            groups[call["purpose"]] = groups.get(call["purpose"], 0) + 1
        research_calls = sum(x.get('attempt_class') == 'research' for x in calls)
        return max(0, sum(n - 1 for n in groups.values()) - research_calls)

    def prepare_turn(self, c, chat, turn):
        if chat['provider'] == 'nebius_token_factory':
            # Explicit paid recoveries share the 20 physical attempts and money
            # admission; a separate three-retry counter must not strand the chat.
            remaining = self.chat.remaining(chat, self.chat.messages(c, chat), c)
            self.research.provider.capacity(c, chat['mission_id'], required=remaining)
            return
        if (
            chat["provider"] != "direct_council"
            or chat["protocol"]["version"] not in ("reviewed_v3", "reviewed_v4")
        ):
            return
        mission = self.store.get(c, chat["mission_id"], "mission")
        start = mission.get("direct_attempt_window", {}).get("start_attempt", 0)
        calls = [
            x
            for x in self.store.list(c, "call", chat["mission_id"])
            if x.get("accounting_provider", x.get("provider")) == chat["provider"]
        ][start:]
        groups = {}
        for call in calls:
            groups[call["purpose"]] = groups.get(call["purpose"], 0) + 1
        purpose = f"chat:{chat['id']}:{turn['key']}"
        recovery_used = self.recovery_usage(c, chat)
        if groups.get(purpose) and recovery_used >= 3:
            raise DomainError(
                "This request's recovery allowance is used. Saved work remains here; continue with a new scoped request or a partial answer.",
                429,
            )
        today = datetime.now(UTC).date().isoformat()
        active = [
            x
            for x in self.store.list(c, "chat_capacity", chat["mission_id"])
            if x["state"] == "active" and x["day"] == today
        ]
        if not active:
            # Renew after a UTC boundary or an explicit recovery, never reset
            # the request's already consumed attempts/recovery counters.
            remaining = self.chat.remaining(chat, self.chat.messages(c, chat), c)
            required = remaining + max(0, 3 - recovery_used)
            if chat.get('research_tools_enabled'):
                required += max(0, mission.get('direct_attempt_window', {}).get('research_call_limit', 5) - sum(x.get('attempt_class') == 'research' for x in calls))
            self.reserve_capacity(c, chat, required)

    def continuation(self, c, chat):
        if chat['provider'] == 'nebius_token_factory':
            try:
                for p in chat['participants']:
                    self.research.budget.verification(c, p['model'])
                value = self.research.budget.summary(c)
                local = self.research.council_preferences.allowance(c, chat)
                allowed = value['remaining_usd'] > 0 and local['remaining_usd'] > 0
                return {'allowed': allowed, 'reason': None if allowed else 'This conversation allowance is used. Add existing-credit allowance here to continue in this chat.' if local['remaining_usd'] <= 0 and value['remaining_usd'] > 0 else 'Token Factory aggregate allowance reached', 'conversation_remaining_usd': local['remaining_usd']}
            except DomainError as error:
                return {'allowed': False, 'reason': error.message}
        if chat["provider"] != "direct_council":
            return None
        required = (
            2 * len(chat["participants"]) + 7
            if chat.get("mode") == "reviewed"
            else len(chat["participants"]) + 1 + RETRY_ALLOWANCE
        )
        if chat.get('research_tools_enabled') or chat.get('research_enabled') or chat.get('next_research_enabled') or self.store.list(c, 'source', chat['mission_id']):
            required = min(20, required + 5)
        try:
            self.research.direct_provider.validate(
                c,
                [p["model"] for p in chat["participants"]],
                chat["mission_id"],
                required=required,
                fresh_window=True,
            )
            return {"allowed": True, "required": required, "reason": None}
        except DomainError as exc:
            return {"allowed": False, "required": required, "reason": exc.message}

    def leader(self, chat, participants):
        return next(
            (p for p in participants if p.get("provider") == "gemini"), participants[0]
        )

    def reassign_unavailable_role(self, c, chat, turn, error, count, used):
        """One disclosed selected-seat reassignment inside the shared reserve."""
        if chat["protocol"]["version"] not in ("reviewed_v3", "reviewed_v4") or turn["phase"] == "opening":
            return None
        if count >= 2 or used - chat.get("retry_window_start", 0) >= 3:
            return None
        if self.recovery_usage(c, chat) >= 3:
            return None
        permitted = {
            "credential",
            "access",
            "account",
            "provider_temporary",
            "network_ambiguous",
            "platform_rate_limit",
            "model_unavailable",
            "request_too_large",
            "output_incomplete",
        }
        if error.kind not in permitted:
            return None
        terminal = not error.retryable and error.kind in {
            "credential",
            "access",
            "account",
            "model_unavailable",
            "request_too_large",
        }
        if not terminal and len(self.failures(c, chat, turn)) < 2:
            return None
        record = self.chat.review.record(c, chat)
        if any(
            x.get("actor") == "bounded_selected_seat_recovery"
            and x["phase"] == turn["phase"]
            and x.get("original_author_id") == turn.get("author_id")
            for x in record["reassignments"]
        ):
            return None
        candidates = [
            p
            for p in self.chat.active_members(chat)
            if p["id"] != turn["participant"]["id"]
        ]
        if not candidates:
            return None
        preferred = self.leader(chat, candidates)
        try:
            self.research.direct_provider.validate(
                c,
                [preferred["model"]],
                chat["mission_id"],
                required=self.chat.remaining(chat, self.chat.messages(c, chat), c),
            )
        except DomainError:
            return None
        change = {
            "phase": turn["phase"],
            "participant_id": preferred["id"],
            "original_author_id": turn.get("author_id"),
            "previous_participant_id": turn["participant"]["id"],
            "reason": error.message,
            "actor": "bounded_selected_seat_recovery",
            "at": now(),
        }
        record["reassignments"].append(change)
        if turn["phase"] != "repair":
            record["roles"][turn["phase"]] = preferred["id"]
            from .db import digest

            record["roles_hash"] = digest(record["roles"])
        record["revision"] += 1
        self.chat.review.engine(chat).save_plan(c, chat, record)
        self.store.event(
            c,
            chat["mission_id"],
            "council.role_reassigned",
            {"chat_id": chat["id"], **change},
        )
        return {**turn, "participant": preferred}

    def effective_member(self, chat, original):
        if chat["provider"] != "nebius_token_factory":
            return original
        override = chat.get("model_overrides", {}).get(original["id"])
        if not override:
            return original
        frozen = next(p for p in chat["participants"] if p["id"] == original["id"])
        target = override["model"]
        approved = self.research.settings.policy.get("authorized_model_replacements", {})
        if approved.get(frozen["model"]) != target or target not in self.research.settings.models:
            raise DomainError("Saved Token Factory replacement is outside the user-authorized policy", 422)
        return {**original, "model": target, "actual_model": target,
                "name": override["name"], "replacement_for": frozen["model"],
                "replacement_name": frozen["name"]}

    def replace_token_factory_member(self, c, cid, member_id, target):
        """Explicit operator change; preserve frozen seats, prior authors and receipts."""
        from .db import now

        chat = self.store.get(c, cid, "chat")
        if chat["provider"] != "nebius_token_factory":
            raise DomainError("This replacement requires a Token Factory council", 422)
        original = next((p for p in chat["participants"] if p["id"] == member_id), None)
        approved = self.research.settings.policy.get("authorized_model_replacements", {})
        if not original or approved.get(original["model"]) != target:
            raise DomainError("The requested replacement is not user-authorized", 422)
        previous = chat.get("model_overrides", {}).get(member_id)
        if previous and previous["model"] == target:
            return chat
        active_call = any(x.get("state") == "dispatching" and x.get("purpose", "").startswith(f"chat:{cid}:") for x in self.store.list(c, "call", chat["mission_id"]))
        if c.execute("SELECT COUNT(*) FROM jobs WHERE target_id=? AND state IN ('queued','running')", (cid,)).fetchone()[0] or chat.get("active_turn") or active_call:
            raise DomainError("Finish the active request before changing its model", 409)
        self.research.budget.verification(c, target)
        replacement = {"model": target, "actual_model": target,
                       "name": self.research.settings.policy.get("council_model_names", {}).get(target, target),
                       "source_model": original["model"], "origin": "explicit_user_model_replacement",
                       "changed_at": now()}
        chat.setdefault("model_overrides", {})[member_id] = replacement
        chat["revision"] += 1
        self.store.put(c, "chat", chat)
        self.store.event(c, chat["mission_id"], "council.model_replaced", {"chat_id": cid, "member_id": member_id, **replacement})
        return chat

    def effective_turn(self, c, chat, turn):
        """Keep the frozen seat and old authors; disclose a replacement on new messages."""
        if chat["provider"] == "nebius_token_factory":
            return {**turn, "participant": self.effective_member(chat, turn["participant"])}
        if chat["provider"] != "direct_council":
            return turn
        original = turn["participant"]
        override = chat.get("model_overrides", {}).get(original["id"])
        if not override:
            # Historical failures count too; explicit resume cannot evade the threshold.
            failures = []
            for call in reversed(self.store.list(c, "call", chat["mission_id"])):
                if call.get("seat_model_id") != original["model"]:
                    continue
                if not self.eligible_failure(call):
                    break
                failures.append(call)
            if len(failures) >= 2 and self.fallback(
                c,
                chat,
                turn,
                "At least two consecutive saved failures from the primary model",
            ):
                override = chat["model_overrides"][original["id"]]
        if not override:
            return turn
        entries = self.research.direct_provider.fallback_entries()
        entry = entries.get(override["model"])
        if not entry or entry["fallback_for"] != original["model"]:
            raise DomainError(
                "Saved model replacement is outside the authorized allowlist", 422
            )
        participant = {
            **original,
            "model": override["model"],
            "actual_model": entry["model"],
            "name": entry["name"],
            "replacement_for": original["model"],
            "replacement_name": original["name"],
        }
        return {**turn, "participant": participant}

    def unavailable(self, c, chat):
        notices = []
        if not chat.get("unavailable_members"):
            return notices
        calls = self.store.list(c, "call", chat["mission_id"])
        for member_id, missing in chat["unavailable_members"].items():
            override = chat.get("model_overrides", {}).get(member_id, {})
            model = override.get("model", missing["model"])
            call = next(
                (x for x in reversed(calls) if x.get("id") == missing.get("call_id") or x.get("seat_model_id") == model), {}
            )
            parts = call.get("purpose", "").split(":")
            notices.append(
                {
                    **missing,
                    "name": override.get("name", missing["name"]),
                    "model": model,
                    "actual_model": call.get(
                        "model",
                        override.get(
                            "actual_model", missing.get("actual_model", model)
                        ),
                    ),
                    "phase": missing.get("phase") or (parts[4] if len(parts) > 4 and parts[2] == "review" else parts[2] if len(parts) > 2 else "turn"),
                    "call_id": call.get("id"),
                }
            )
        return notices

    def failures(self, c, chat, turn):
        purpose = f"chat:{chat['id']}:{turn['key']}"
        return [
            x
            for x in self.store.list(c, "call", chat["mission_id"])
            if x.get("purpose") == purpose
            and x.get("state") in ("failed", "unknown")
            and x.get("seat_model_id") == turn["participant"]["model"]
            and self.eligible_failure(x)
        ]

    @staticmethod
    def eligible_failure(call):
        return call.get("state") in ("failed", "unknown") and (
            call.get("http_status") in (408, 413, 429, 500, 502, 503, 504)
            or call.get("state") == "unknown"
            or call.get("finish_reason") in ("length", "MAX_TOKENS")
        )

    def fallback(self, c, chat, turn, reason):
        member = turn["participant"]
        if member["id"] in chat.get("model_overrides", {}):
            return False
        candidate = next(
            (
                (mid, entry)
                for mid, entry in self.research.direct_provider.fallback_entries().items()
                if entry["fallback_for"] == member["model"]
            ),
            None,
        )
        if not candidate:
            return False
        mid, entry = candidate
        if self.store.setting(c, "direct_locked:" + entry["provider"], False):
            return False
        change = {
            "model": mid,
            "name": entry["name"],
            "actual_model": entry["model"],
            "original_model": member["model"],
            "reason": reason,
            "created_at": now(),
            "after_failures": 2,
        }
        chat.setdefault("model_overrides", {})[member["id"]] = change
        self.store.event(
            c,
            chat["mission_id"],
            "chat.model_replaced",
            {"chat_id": chat["id"], "participant_id": member["id"], **change},
        )
        self.store.put(c, "chat", chat)
        return True


def groq_discussion_context(payload, maximum=10500):
    """A declared excerpt window. Never rewrite the saved transcript or latest request."""
    value = dict(payload)
    value["context_policy"] = (
        "Groq free-tier context window: source answers are excerpts, not complete texts. "
        "The full transcript stays saved. Missing text is not agreement or evidence. "
        "Answer the latest director request; label conclusions that need omitted context."
    )
    # Preserve the complete question and the latest director instruction. Balance peers.
    value["director_notes"] = payload.get("director_notes", [])[-1:]
    for width in (1000, 600, 300, 120, 0):
        value["shared_baseline"] = [
            {**m, "answer": m["answer"][:width], "excerpted": len(m["answer"]) > width}
            for m in payload.get("shared_baseline", [])
        ]
        value["discussion_so_far"] = (
            [
                {
                    **m,
                    "answer": m["answer"][:width],
                    "excerpted": len(m["answer"]) > width,
                }
                for m in payload.get("discussion_so_far", [])[-4:]
            ]
            if width
            else []
        )
        prompt = json.dumps(value, ensure_ascii=False)
        if len(prompt.encode()) <= maximum:
            ids = [
                m["id"]
                for key in ("shared_baseline", "discussion_so_far", "director_notes")
                for m in value.get(key, [])
            ]
            return prompt, ids
    raise DomainError(
        "The question and latest message exceed Groq's free request window. Shorten the message in this same chat; saved replies remain available.",
        422,
    )
