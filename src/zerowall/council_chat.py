"""A durable, visible conversation: independent openings, sequential debate, synthesis."""

import json
from datetime import UTC, datetime, timedelta

from .contracts import MissionBrief
from .db import DomainError, digest, now, uid
from .free_errors import FreeProviderError
from .free_limits import CHAT_MAX_ATTEMPTS, RETRIES_PER_TURN, RETRY_ALLOWANCE
from .free_provider import CHAT_MODELS, OpenRouterFreeProvider
from .resource_policy import limits as resource_limits
from .thinking_levels import LEVELS
from .thinking_levels import projection as thinking_projection
from .token_factory_generation import profile as token_factory_profile

LABELS = {
    "nvidia/nemotron-3-super-120b-a12b:free": "Nemotron Super",
    "google/gemma-4-31b-it:free": "Gemma 4",
    "xingchen-agi/xing4.0-29b-a4b:free": "Xing 4",
    "nvidia/nemotron-3.5-lightning:free": "Nemotron Lightning",
    "demo/analyst": "Demo Analyst",
    "demo/critic": "Demo Critic",
    "demo/builder": "Demo Builder",
}
DEMO_MODELS = ("demo/analyst", "demo/critic", "demo/builder")
READY = "[[COUNCIL_READY]]"


class CouncilChat:
    @staticmethod
    def planned_calls(body):
        return (
            2 * len(body.models) + 4
            if body.mode == "reviewed"
            else len(body.models) * (1 + body.max_rounds) + 1
        )

    def start_allowance(self, body):
        return self.planned_calls(body) + (5 if body.search_web or body.research_tools else 0) + (
            RETRY_ALLOWANCE
            if body.mode == "reviewed" or body.provider == "direct_council"
            else 0
        )

    def preview(self, c, body):
        from .council_web_search import resolve_default
        body = resolve_default(self, body)
        planned = self.planned_calls(body)
        result = {
            "research_calls": 5 if body.search_web or body.research_tools else 0,
            "planned_calls": planned,
            "required_start": self.start_allowance(body),
            "retry_allowance": RETRY_ALLOWANCE,
            "blocked": False,
            "reason": None,
            "role_names": {},
            "review_protocol": body.review_protocol
            if body.mode == "reviewed"
            else None,
            "claims_per_author": 2 if body.review_protocol in ("reviewed_v2", "reviewed_v3", "reviewed_v4") else 4,
            "display_name": "Council",
        }
        try:
            if body.provider == "direct_council":
                self.research.direct_provider.validate(
                    c, body.models, required=result["required_start"]
                )
            elif body.provider == "nebius_token_factory":
                for model in body.models:
                    self.research.budget.verification(c, model)
            elif body.provider == "openrouter_free":
                if not self.settings.openrouter_enabled:
                    raise DomainError("OpenRouter is disabled", 412)
                self.research.free_provider.capacity(
                    c, required=result["required_start"]
                )
            if body.mode == "reviewed":
                entries = self.research.direct_provider.entries()
                order = (
                    list(entries)
                    if body.provider == "direct_council"
                    else list(DEMO_MODELS)
                    if body.provider == "fixture"
                    else self.settings.models
                    if body.provider == "nebius_token_factory"
                    else list(CHAT_MODELS)
                )
                members = [
                    {
                        "id": f"member_{i + 1}",
                        "model": mid,
                        "provider": entries[mid]["provider"]
                        if mid in entries
                        else None,
                        "name": entries[mid]["name"]
                        if mid in entries
                        else LABELS.get(mid, mid),
                    }
                    for i, mid in enumerate(sorted(body.models, key=order.index))
                ]
                if body.review_protocol in ("reviewed_v3", "reviewed_v4"):
                    from .council_review_v3 import UnifiedCouncil
                    roles = UnifiedCouncil.roles_for(members)
                else:
                    roles = self.review.roles_for(members)
                result["role_names"] = {
                    phase: next(p["name"] for p in members if p["id"] == member)
                    for phase, member in roles.items()
                }
        except (DomainError, ValueError) as exc:
            result.update(
                blocked=True,
                reason=exc.message
                if isinstance(exc, DomainError)
                else "A selected model is outside this provider's allowlist",
            )
        return result

    def __init__(self, research):
        self.research = research
        self.store, self.settings = research.store, research.settings
        from .council_review import CouncilReview

        self.review = CouncilReview(self)
        from .council_runtime import CouncilRuntime
        self.runtime = CouncilRuntime(self)
        from .output_recovery import OutputRecovery
        self.output_recovery = OutputRecovery(self)

    def bootstrap(self, c):
        from .token_factory_prices import PRICE_CACHE_DAYS
        verification = self.store.setting(c, "live_verification", {})
        factory_preferred = bool(verification.get("authorization_mode") == "existing_credit_testing"
                                 and self.research.budget.funding_confirmed(c, verification)) or bool(self.store.remote and self.settings.api_key)
        verified = []
        for model in self.settings.models:
            try:
                self.research.budget.verification(c, model)
                verified.append(model)
            except DomainError:
                pass
        capacity = self.research.free_provider.capacity(c, required=0)
        return {
            "chats": [
                json.loads(row[0])
                for row in c.execute(
                    "SELECT body FROM records WHERE kind='chat' ORDER BY rowid DESC"
                )
            ],
            "research": {"configured": bool(self.settings.tavily_api_key), "default_enabled": bool(self.settings.tavily_api_key), "max_searches": 3, "extra_model_calls": 5, "monthly_ceiling": self.settings.search_monthly_limit},
            "providers": {
                "direct_council": self.research.direct_provider.bootstrap(c),
                "openrouter_free": {
                    "enabled": self.settings.openrouter_enabled,
                    "configured": self.settings.openrouter_enabled
                    and bool(self.settings.openrouter_api_key),
                    "ready": self.settings.openrouter_enabled
                    and bool(self.settings.openrouter_api_key)
                    and not self.store.setting(c, "openrouter_free_locked", False)
                    and capacity["daily_remaining"] >= 5,
                    "models": [{"id": m, "name": LABELS[m]} for m in CHAT_MODELS],
                    "daily_remaining": capacity["daily_remaining"],
                    "attempt_cap": CHAT_MAX_ATTEMPTS,
                    "retry_allowance": RETRY_ALLOWANCE,
                    "account": self.research.free_provider.cached_account(c),
                },
                "nebius_token_factory": {
                    "configured": bool(self.settings.api_key),
                    "preferred": factory_preferred,
                    "price_cache_days": PRICE_CACHE_DAYS,
                    "price_expires_at": verification.get("expires_at"),
                    "price_refresh": self.store.setting(c, "token_factory_price_refresh", {}),
                    "ready": len(verified) >= 2,
                    "models": [
                        {"id": m, "name": self.settings.policy.get("council_model_names", {}).get(m, m.split("/")[-1]), "selection_notice": self.settings.policy.get("council_model_notices", {}).get(m)}
                        for m in self.settings.models
                        if m not in self.settings.policy.get("retired_council_models", [])
                    ],
                    "verified_models": verified,
                    "default_models": [m for m in self.settings.policy.get("council_default_models", self.settings.models) if m in self.settings.models and m not in self.settings.policy.get("retired_council_models", [])],
                    "generation": {"opening": "raw_opening", "review": "controlled_review", "full_review_follows": True, "context_tokens": self.settings.token_factory_generation["context_tokens"]},
                    "thinking_profiles": {level: thinking_projection(self.settings, self.settings.models, level) for level in LEVELS},
                },
                "fixture": {
                    "ready": True,
                    "models": [{"id": m, "name": LABELS[m]} for m in DEMO_MODELS],
                },
            },
        }

    def create(self, c, body):
        from .council_web_search import resolve_default
        body = resolve_default(self, body)
        self.research.library.check_secret(body.search_query)
        if body.search_web and (body.provider not in ('direct_council', 'nebius_token_factory') or body.mode != 'reviewed' or body.review_protocol not in ('reviewed_v3', 'reviewed_v4')):
            raise DomainError('Web research requires the current Council', 422)
        if body.search_web and not self.settings.tavily_api_key:
            raise DomainError('Web search is unavailable; saved or supplied sources still work', 412)
        if body.provider == "openrouter_free" and not self.settings.openrouter_enabled:
            raise DomainError(
                "OpenRouter is disabled. Select the direct provider council or a synthetic demo.",
                412,
            )
        allowed = (
            tuple(self.research.direct_provider.entries())
            if body.provider == "direct_council"
            else CHAT_MODELS
            if body.provider == "openrouter_free"
            else DEMO_MODELS
            if body.provider == "fixture"
            else self.settings.models
        )
        if not set(body.models) <= set(allowed):
            raise DomainError(
                "A selected model is outside this provider's council allowlist", 422
            )
        models = sorted(body.models, key=allowed.index)
        if body.provider == "direct_council":
            required = self.start_allowance(body)
            self.research.direct_provider.validate(c, models, required=required)
        if body.provider == "nebius_token_factory":
            if body.budget_usd <= 0:
                raise DomainError(
                    "Token Factory requires a positive existing-credit allowance and verified billing",
                    412,
                )
            for model in body.models:
                self.research.budget.verification(c, model)
        elif body.provider == "openrouter_free":
            self.research.free_provider.choose(c, check_backoff=False)
        prompt = self.research.artifacts.redact(body.prompt.strip())
        brief = MissionBrief(
            title=(
                prompt.splitlines()[0]
                if len(prompt.splitlines()[0]) >= 3
                else "Council: " + prompt
            )[:120],
            goal=prompt if len(prompt) >= 10 else "Discuss this question: " + prompt,
            deliverable="A final answer grounded in independent proposals and visible deliberation.",
            constraints=[
                "Use only the selected provider and frozen participants.",
                "No additional payment or rented GPU.",
                "Preserve disagreements and distinguish proposals from verified facts.",
            ],
            rubric=[
                "Answer the original question",
                "Challenge substantive assumptions",
                "Preserve unresolved disagreement",
            ],
            steps=[{"key": "discussion", "title": "Council discussion"}],
            mode="fixture" if body.provider == "fixture" else "live",
            provider="nebius_token_factory"
            if body.provider == "fixture"
            else body.provider,
            openrouter_model=models[0] if body.provider == "openrouter_free" else None,
            budget_usd=body.budget_usd,
        )
        mission = self.research.create_mission(c, brief)
        mission["surface"] = "chat"
        mission["spending_scope"] = body.spending_scope
        self.store.put(c, "mission", mission)
        self.research.freeze(c, mission["id"], 1)
        step = self.store.list(c, "step", mission["id"])[0]
        participants = [
            {
                "id": f"member_{i + 1}",
                "model": model,
                "name": self.settings.policy.get("council_model_names", {}).get(model, LABELS.get(model, model.split("/")[-1])),
            }
            for i, model in enumerate(models)
        ]
        if body.provider == "direct_council":
            entries = self.research.direct_provider.entries()
            for p in participants:
                p.update(
                    name=entries[p["model"]]["name"],
                    provider=entries[p["model"]]["provider"],
                    actual_model=entries[p["model"]]["model"],
                )
        if body.provider == 'nebius_token_factory':
            for participant in participants:
                participant.update(provider='nebius_token_factory', actual_model=participant['model'])
        protocol = {
            "version": body.review_protocol
            if body.mode == "reviewed"
            else "discussion_v1",
            "mode": body.mode,
            "prompt": prompt,
            "provider": body.provider,
            "participants": participants,
            "initial_max_rounds": body.max_rounds,
            "budget_usd": body.budget_usd,
        }
        chat = {
            "spending_scope": body.spending_scope,
            "execution_descriptor": {"version": "research/1", "accounting": "usage/1", "source_policy": "scoped/1", "parallel_openings": False},
            "research_enabled": body.search_web,
            "collective_research_enabled": bool(body.search_web and body.collective_research),
            **({"web_search_policy": "per-reply-search/1"} if body.search_web else {}),
            "research_tools_enabled": body.search_web or body.research_tools,
            "research_query": body.search_query.strip() if body.search_web else '',
            "mode": body.mode,
            "id": uid("chat"),
            "mission_id": mission["id"],
            "step_id": step["id"],
            "step_revision": 1,
            "title": brief.title,
            "provider": body.provider,
            "participants": participants,
            "original_prompt": prompt,
            "protocol": protocol,
            "protocol_hash": digest(protocol),
            "max_rounds": body.max_rounds,
            "generation": 0,
            "thinking_level": body.thinking_level,
            "status": "paused" if body.defer_start else "running",
            "active_turn": None,
            "requested_finish": False,
            "revision": 1,
            "accepted": False,
            "final_message_id": None,
            "unavailable_members": {},
            "retry_counts": {},
            "retry_used": 0,
            "retry_wait": None,
        }
        chat['execution_descriptor_hash'] = digest(chat['execution_descriptor'])
        if protocol["version"] == "reviewed_v4":
            chat["execution_descriptor"].update(delivery="answer-delivery/1", annotations="answer-first/1")
            chat["execution_descriptor_hash"] = digest(chat["execution_descriptor"])
        if body.provider == "openrouter_free":
            self.research.free_provider.capacity(
                c, mission["id"], required=self.start_allowance(body)
            )
        self.store.put(c, "chat", chat)
        self.runtime.begin_window(c, chat, self.start_allowance(body), "initial_request")
        if body.mode == "reviewed":
            self.review.initialize(c, chat, body.review_options)
        self.message(c, chat, role="user", content=prompt, phase="prompt")
        if not body.defer_start:
            self.research.enqueue(c, "chat", chat)
        self.store.event(
            c,
            mission["id"],
            "chat.created",
            {
                "chat_id": chat["id"],
                "provider": body.provider,
                "protocol_hash": chat["protocol_hash"],
            },
        )
        return self.view(c, chat["id"])

    def messages(self, c, chat):
        return self.store.list(c, "chat_message", chat["mission_id"])

    def message(self, c, chat, **values):
        defer_annotations = values.pop("defer_annotations", False)
        message = {
            "id": uid("message"),
            "mission_id": chat["mission_id"],
            "chat_id": chat["id"],
            "sequence": len(self.messages(c, chat)) + 1,
            **({"context_branch_id": chat["context_branch_id"]} if chat.get("context_branch_id") else {}),
            **values,
        }
        message["content"] = self.research.artifacts.redact(message["content"])
        if message.get("call_id") and "web_search" not in message and c.execute("SELECT 1 FROM records WHERE id=? AND kind='call'", (message["call_id"],)).fetchone():
            call = self.store.get(c, message["call_id"], "call")
            if call.get("web_search"):
                message["web_search"] = call["web_search"]
        if not defer_annotations and message.get('role') == 'assistant' and chat.get('execution_descriptor'):
            message['research_citations'] = self.research.library.bind_message(c, chat, message)
            self.research.library.rechecked(c, chat, message)
        self.store.put(c, "chat_message", message)
        self.store.event(
            c,
            chat["mission_id"],
            "chat.message",
            {"chat_id": chat["id"], "message_id": message["id"]},
        )
        return message

    def active_members(self, chat):
        missing = chat.get("unavailable_members", {})
        return [self.runtime.effective_member(chat, p) for p in chat["participants"] if p["id"] not in missing]

    def next_turn(self, chat, messages, c=None):
        if chat.get("mode") == "reviewed":
            if c is None:
                with self.store.tx() as connection:
                    return self.review.next_turn(connection, chat, messages)
            return self.review.next_turn(c, chat, messages)
        replies = {m["turn_key"]: m for m in messages if m.get("turn_key")}
        participants = self.active_members(chat)
        final_round = 0
        if not chat["requested_finish"]:
            for participant in participants if not chat.get("generation") else []:
                key = "opening:" + participant["id"]
                if key not in replies:
                    return {
                        "phase": "opening",
                        "round": 0,
                        "participant": participant,
                        "key": key,
                    }
            for number in range(chat.get("discussion_start_round", 1), chat["max_rounds"] + 1):
                for participant in participants:
                    key = f"debate:{number}:" + participant["id"]
                    if key not in replies:
                        return {
                            "phase": "debate",
                            "round": number,
                            "participant": participant,
                            "key": key,
                        }
                final_round = number
        else:
            final_round = max(
                (m.get("round", 0) for m in messages if m.get("phase") == "debate"),
                default=0,
            )
        key = "final:" + str(chat["generation"])
        if key not in replies:
            return {
                "phase": "synthesis",
                "round": final_round,
                "participant": self.runtime.leader(chat, participants or chat["participants"]),
                "key": key,
            }
        return None

    def remaining(self, chat, messages, c=None):
        if chat.get("mode") == "reviewed":
            if c is None:
                with self.store.tx() as connection:
                    return self.review.remaining(connection, chat, messages)
            return self.review.remaining(c, chat, messages)
        if any(
            m.get("turn_key") == "final:" + str(chat["generation"]) for m in messages
        ):
            return 0
        if chat["requested_finish"]:
            return 1
        keys = {m.get("turn_key") for m in messages}
        return (
            (sum("opening:" + p["id"] not in keys for p in self.active_members(chat)) if not chat.get("generation") else 0)
            + sum(
                f"debate:{number}:" + p["id"] not in keys
                for number in range(chat.get("discussion_start_round", 1), chat["max_rounds"] + 1)
                for p in self.active_members(chat)
            )
            + int("final:" + str(chat["generation"]) not in keys)
        )

    def add_message(self, c, cid, body):
        chat = self.store.get(c, cid, "chat")
        if chat.get("protocol", {}).get("version") == "reviewed_v4" and chat["status"] in ("running", "waiting"):
            self.store.put(c, "chat_steering", {"id": uid("steering"), "mission_id": chat["mission_id"],
                "chat_id": cid, "text": self.research.artifacts.redact(body.text.strip()), "state": "queued",
                "requested_during": chat.get("active_turn"), "applies_at": "next_completed_turn_or_opening_barrier"})
            return self.view(c, cid)
        if body.review_protocol and chat["protocol"]["version"] != body.review_protocol:
            return self.review.adopt_scoped(c, chat, body.text, body.review_protocol)
        if chat["protocol"]["version"] in ("reviewed_v3", "reviewed_v4") and body.action != "review":
            return self.review.engine(chat).followup(c, chat, body)
        messages = self.messages(c, chat)
        if (chat.get("active_turn") or {}).get("phase") == "synthesis":
            raise DomainError(
                "The final synthesis is being written. Send a follow-up after this turn completes."
            )
        if chat["status"] == "cancelled" and chat["provider"] not in ("direct_council", "nebius_token_factory"):
            raise DomainError(
                "This council was stopped. Start a new council to continue."
            )
        if chat["final_message_id"] or (chat["provider"] in ("direct_council", "nebius_token_factory") and chat["status"] in ("cancelled", "failed", "unavailable", "interrupted")):
            if chat.get("mode") == "reviewed":
                return self.review.new_cycle(c, chat, body.text.strip())
            self.runtime.begin_window(c, chat, len(chat["participants"]) + 1 + RETRY_ALLOWANCE, "user_followup")
            if chat["provider"] == "direct_council":
                chat["unavailable_members"] = {}
            chat["max_rounds"] = (
                max(
                    (m.get("round", 0) for m in messages if m.get("phase") == "debate"),
                    default=0,
                )
                + 1
            )
            chat["generation"] += 1
            chat["discussion_start_round"] = chat["max_rounds"]
            chat.update(final_message_id=None, requested_finish=False, accepted=False)
            if chat["max_rounds"] > 6 and chat["provider"] not in ("direct_council", "nebius_token_factory"):
                raise DomainError(
                    "This council reached its discussion limit; start a new council"
                )
            if chat["provider"] == "openrouter_free":
                self.research.free_provider.capacity(
                    c, chat["mission_id"], required=len(self.active_members(chat)) + 1
                )
            elif chat["provider"] == "direct_council":
                self.research.direct_provider.validate(
                    c,
                    [p["model"] for p in self.active_members(chat)],
                    chat["mission_id"],
                    required=len(self.active_members(chat)) + 1,
                )
            chat["status"] = "running"
            chat.update(error=None, retry_wait=None)
            step = self.store.get(c, chat["step_id"], "step")
            step.update(paused=False, status="committing")
            self.store.put(c, "step", step)
            self.research.enqueue(c, "chat", chat)
        self.message(
            c,
            chat,
            role="user",
            content=body.text.strip(),
            phase="intervention",
            review_cycle=chat.get("review_cycle"),
        )
        if chat.get("mode") == "reviewed":
            review = self.review.record(c, chat)
            review.update(
                revision=review["revision"] + 1,
                stale=any(m.get("phase") == "recheck" for m in messages),
            )
            self.store.put(c, "chat_review", review)
        chat["revision"] += 1
        self.store.put(c, "chat", chat)
        return self.view(c, cid)

    def edit_message(self, c, cid, mid, body):
        from .council_message_edits import regenerate
        return regenerate(self, c, cid, mid, body)

    def control(self, c, cid, body):
        chat = self.store.get(c, cid, "chat")
        step = self.store.get(c, chat["step_id"], "step")
        messages = self.messages(c, chat)
        if body.action == "accept":
            if self.research.library.pending_changes(c, chat):
                raise DomainError('A referenced source changed. Request an updated review before accepting the current answer.', 409)
            if not chat["final_message_id"]:
                raise DomainError("Wait for the final synthesis before accepting it")
            if chat.get("mode") == "reviewed" and self.review.record(c, chat).get(
                "synthesis_stale"
            ):
                raise DomainError(
                    "The answer predates review changes. Update the final answer before accepting it."
                )
            chat.update(accepted=True, accepted_at=now())
        elif body.action in ("pause", "stop"):
            if chat["status"] == "completed":
                return self.view(c, cid)
            chat["status"] = "paused" if body.action == "pause" else "cancelled"
            if body.action == "stop":
                chat.pop("pending_request_recovery", None)
            if body.action == "stop" and chat.get("protocol", {}).get("version") == "reviewed_v4":
                from .answer_budget import release
                release(self, c, chat)
            step["paused"] = True
            c.execute(
                "UPDATE jobs SET state='cancelled' WHERE target_id=? AND state='queued'",
                (cid,),
            )
        else:
            if body.action == "recover_output":
                self.output_recovery.authorize(c, chat, body.recovery_call_id)
            else:
                chat.pop("pending_output_recovery", None)
            if chat["status"] == "cancelled":
                raise DomainError("This council was stopped; create a new council")
            if chat["status"] == "completed":
                return self.view(c, cid)
            if body.action == "continue_without_model":
                from .token_factory_recovery import continue_without_model
                continue_without_model(self, c, chat, body)
            if body.action == "finish":
                if not any(m["role"] == "assistant" for m in messages):
                    raise DomainError(
                        "Wait for at least one opening answer before synthesizing"
                    )
                chat["requested_finish"] = True
                chat.pop("pending_request_recovery", None)
                if chat.get("mode") == "reviewed":
                    review = self.review.record(c, chat)
                    review["partial_reasons"].append(
                        "Director requested synthesis before the full review schedule completed"
                    )
                    if review["roles"]["synthesis"] in chat.get(
                        "unavailable_members", {}
                    ) and self.active_members(chat):
                        member = self.active_members(chat)[0]
                        review["roles"]["synthesis"] = member["id"]
                        review["roles_hash"] = digest(review["roles"])
                        review["reassignments"].append(
                            {
                                "phase": "synthesis",
                                "participant_id": member["id"],
                                "original_author_id": None,
                                "reason": "Director explicitly requested a partial synthesis from saved work",
                                "at": now(),
                                "actor": "human_director",
                            }
                        )
                    self.store.put(c, "chat_review", review)
            if chat["status"] == "completed":
                return self.view(c, cid)
            if chat["provider"] == "direct_council":
                if (
                    body.action == "resume"
                    and chat.get("protocol", {}).get("version") in ("reviewed_v2", "reviewed_v3", "reviewed_v4")
                    and chat["status"] in ("failed", "unavailable")
                    and not chat.get("requested_finish")
                    and chat.get("unavailable_members")
                ):
                    review = self.review.record(c, chat)
                    review.setdefault("recovery_history", []).append(
                        {
                            "at": now(),
                            "actor": "explicit_resume",
                            "members": chat["unavailable_members"],
                            "prior_partial_reasons": review.get("partial_reasons", []),
                        }
                    )
                    chat["unavailable_members"] = {}
                    review["skipped_keys"] = []
                    review["partial_reasons"] = [
                        reason
                        for reason in review.get("partial_reasons", [])
                        if " unavailable: " not in reason
                    ]
                    review["revision"] += 1
                    self.store.put(c, "chat_review", review)
                self.research.direct_provider.validate(
                    c,
                    [p["model"] for p in self.active_members(chat)],
                    chat["mission_id"],
                    required=self.remaining(chat, messages, c),
                )
            elif chat["provider"] == "openrouter_free":
                if not self.settings.openrouter_enabled:
                    raise DomainError(
                        "OpenRouter is disabled; historical replies remain readable.",
                        412,
                    )
                self.research.free_provider.choose(c, check_backoff=False)
                if chat["status"] == "unavailable" and not chat.get("requested_finish"):
                    chat["unavailable_members"] = {}
                self.research.free_provider.capacity(
                    c, chat["mission_id"], required=self.remaining(chat, messages, c)
                )
            elif chat["provider"] == "nebius_token_factory":
                unknown = any(
                    x["state"] == "unknown" and x["purpose"].startswith(f"chat:{cid}:")
                    for x in self.store.list(c, "call", chat["mission_id"])
                )
                if unknown and not body.authorize_retry_with_unknown_charge:
                    raise DomainError(
                        "An earlier paid request has an unknown charge. Explicit acknowledgement is required before retrying."
                    )
                for p in chat["participants"]:
                    self.research.budget.verification(c, p["model"])
            if body.action == "finish":
                c.execute(
                    "UPDATE jobs SET state='cancelled' WHERE target_id=? AND state='queued'",
                    (cid,),
                )
                chat["retry_wait"] = None
            waiting = chat.get("retry_wait")
            still_waiting = waiting and waiting["not_before"] > now()
            chat.update(status="waiting" if still_waiting else "running", error=None)
            step.update(paused=False, status="committing")
            active = c.execute(
                "SELECT COUNT(*) FROM jobs WHERE target_id=? AND state IN ('queued','running')",
                (cid,),
            ).fetchone()[0]
            if not active:
                chat["active_turn"] = None
                if self.next_turn(chat, messages, c):
                    jid = self.research.enqueue(c, "chat", chat)
                    if still_waiting:
                        c.execute(
                            "UPDATE jobs SET body=? WHERE id=?",
                            (json.dumps({"not_before": waiting["not_before"]}), jid),
                        )
                else:
                    chat["status"] = "completed"
        chat["revision"] += 1
        if chat["status"] in ("completed", "cancelled"):
            self.runtime.release_capacity(c, chat["mission_id"], chat["status"])
        self.store.put(c, "step", step)
        self.store.put(c, "chat", chat)
        self.store.event(
            c,
            chat["mission_id"],
            "chat.control",
            {"chat_id": cid, "action": body.action},
        )
        return self.view(c, cid)

    def view(self, c, cid):
        from .token_factory_recovery import preview as model_recovery_preview
        chat = self.store.get(c, cid, "chat")
        from .collective_research import snapshot as collective_snapshot
        messages = self.messages(c, chat)
        # Only advertise availability here. Fetch large originals on demand,
        # keeping polling and streaming payloads small.
        deliveries = dict(c.execute(
            "SELECT json_extract(body,'$.message_id'), json_extract(body,'$.raw_public_hash') "
            "FROM records WHERE kind='answer_delivery' AND mission_id=? "
            "AND json_extract(body,'$.chat_id')=?", (chat["mission_id"], cid)
        ).fetchall())
        messages = [{**m, "original_response_available": m["id"] in deliveries,
                     "presentation_changed": bool(m["id"] in deliveries and
                         deliveries[m["id"]] != m.get("content_hash"))}
                    for m in messages]
        if chat.get("context_branch_id"):
            from .council_message_edits import on_path
            current_ids = {m["id"] for m in on_path(self, c, chat, messages)}
            messages = [{**m, "superseded": m["id"] not in current_ids} for m in messages]
        active = next((x for x in reversed(self.store.list(c, "call", chat["mission_id"]))
                       if x["state"] == "dispatching" and x.get("purpose", "").startswith(f"chat:{cid}:")), None)
        openings = [m for m in messages if m.get("phase") == "opening" and (chat.get("mode") != "reviewed" or m.get("review_cycle") == chat.get("review_cycle"))]
        return {
            "collective_research": collective_snapshot(self.research, c, chat),
            "model_recovery": model_recovery_preview(self, c, chat),
            "stage_results": [x for x in self.store.list(c, "stage_result", chat["mission_id"]) if x["chat_id"] == cid],
            "queued_steering": [x for x in self.store.list(c, "chat_steering", chat["mission_id"]) if x["state"] == "queued"],
            "public_streams": [{**x, "chunks": x["chunks"][:64], "preview_complete": len(x["chunks"]) <= 64}
                               for x in self.store.list(c, "public_stream", chat["mission_id"])
                               if active and x.get("call_id") == active["id"]],
            "context_status": self.research.context_compaction.status(c, chat),
            "thinking": self.research.council_preferences.thinking(chat),
            "conversation_allowance": self.research.council_preferences.allowance(c, chat),
            "active_request": {
                "call_id": active["id"],
                "model": active["model"],
                "sent_at": active.get("sent_at"),
                "stream_progress": active.get("stream_progress"),
            } if active else None,
            "output_recovery": self.output_recovery.snapshot(c, chat),
            "accounting": self.research.accounting.projection(c, chat),
            "library": self.research.library.view(c, chat),
            "research_tools": self.store.list(c, 'tool_invocation', chat['mission_id']),
            "research_limitations": [{"id": x["id"], "name": x["name"], "state": x["state"]} for x in self.store.list(c, "tool_invocation", chat["mission_id"]) if x["state"] in ("unknown", "failed", "blocked")],
            "resource_policy": {'limits': resource_limits(chat), 'reservations': self.store.list(c, 'resource_reservation', chat['mission_id'])},
            "context_packs": self.store.list(c, 'context_pack', chat['mission_id']),
            "review": self.review.snapshot(c, chat)
            if chat.get("mode") == "reviewed"
            else None,
            "chat": chat,
            "effective_members": [self.runtime.effective_member(chat, p) for p in chat["participants"]]
            if chat["provider"] == "nebius_token_factory" and chat.get("model_overrides") else None,
            "messages": messages,
            "baseline": openings
            if all(
                any(m.get("participant_id") == p["id"] for m in openings)
                for p in self.active_members(chat)
            )
            else [],
            "active_members": self.active_members(chat),
            "retry_allowance": RETRY_ALLOWANCE,
            "degraded": bool(chat.get("unavailable_members")),
            "account": self.research.free_provider.cached_account(c)
            if chat["provider"] == "openrouter_free"
            else None,
            "budget": self.research.budget_summary(c, chat["mission_id"]),
            "continuation": self.runtime.continuation(c, chat),
            "review_adoption": self.review.adoption_preview(c, chat),
            "direct_capacity": self.research.direct_provider.capacity(c, chat["mission_id"]) if chat["provider"] == "direct_council" else None,
            "participation_notices": self.runtime.unavailable(c, chat),
            "lead": self.runtime.leader(chat, self.active_members(chat) or chat["participants"]),
            "next_turn": self.next_turn(chat, messages, c),
            "remaining_planned_calls": self.remaining(chat, messages, c),
            "unknown_paid_attempts": sum(
                x["state"] == "unknown"
                for x in self.store.list(c, "call", chat["mission_id"])
            )
            if chat["provider"] == "nebius_token_factory"
            else 0,
        }

    def output_limit(self, chat, turn):
        if chat["provider"] == "nebius_token_factory":
            return token_factory_profile(self.settings, turn, recovery=bool(chat.get("pending_output_recovery")), thinking_level=chat.get("thinking_level", "balanced"))["requested_output_tokens"]
        if chat["protocol"]["version"] in ("reviewed_v3", "reviewed_v4"):
            limit = {"opening": 2048, "extraction": 6144, "scrutiny": 4096, "repair": 4096, "recheck": 6144, "synthesis": 4096}[turn["phase"]]
            return min(limit, 3072) if turn["participant"].get("provider") == "groq" else limit
        if chat.get("mode") == "reviewed":
            return 4096
        if chat["provider"] == "direct_council":
            if turn["participant"].get("provider") == "groq" and chat.get("mode") != "reviewed":
                return chat.get("groq_output_limit", 3072)
            return 4096 if turn["phase"] == "synthesis" else 3072
        final = turn["phase"] == "synthesis"
        if chat["provider"] == "openrouter_free":
            return 4096 if final else 3072
        return 1400 if final else 1000

    def prompt(self, chat, messages, turn, c=None):
        if chat.get("context_branch_id"):
            if c is None:
                with self.store.tx() as connection:
                    return self.prompt(chat, messages, turn, connection)
            from .council_message_edits import on_path
            messages = on_path(self, c, chat, messages)
        if chat["provider"] == "nebius_token_factory" and turn["phase"] == "opening":
            if c is None:
                with self.store.tx() as connection:
                    return self.prompt(chat, messages, turn, connection)
            question = self.review.record(c, chat)["contract"]["question"] if chat.get("mode") == "reviewed" else chat["original_prompt"]
            notes = [m for m in messages if m["role"] == "user" and m.get("phase") == "intervention" and m.get("review_cycle") == chat.get("review_cycle")]
            prior = [m for m in messages if m["role"] == "user" and m.get("phase") == "intervention" and m.get("review_cycle") != chat.get("review_cycle") and m["content"] not in question]
            notes = [m for m in notes if m["content"] not in question]
            raw = question + ("\n\nEarlier user requests in this conversation:\n" + "\n".join(m["content"] for m in prior) if prior else "") + ("\n\nAdditional user instructions:\n" + "\n".join(m["content"] for m in notes) if notes else "")
            checkpoint = self.review.record(c, chat).get("conversation_checkpoint") if chat.get("mode") == "reviewed" else None
            if checkpoint:
                raw += "\n\nHistorical council checkpoint (prior public assessments, not new evidence):\n" + json.dumps(checkpoint, ensure_ascii=False, separators=(",", ":"))
            return raw, [m["id"] for m in messages if m["role"] == "user" and (m["phase"] == "prompt" or m["content"] in question or m in notes or m in prior)]
        if chat.get("mode") == "reviewed":
            return self.review.prompt(c, chat, messages, turn)
        opening = next(m for m in messages if m["phase"] == "prompt")
        context_ids = [opening["id"]]
        payload = {
            "output_format": "Readable Markdown prose, not a JSON object. Use $...$ inline and $$...$$ on separate lines for equations.",
            "original_question": chat["original_prompt"],
            "you": turn["participant"],
            "phase": turn["phase"],
            "early_synthesis": bool(chat.get("requested_finish")),
            "round": turn["round"],
            "members": self.active_members(chat),
            "unavailable_members": chat.get("unavailable_members", {}),
            "response_budget": {
                "maximum_output_tokens": self.output_limit(chat, turn),
                "target_words": 900 if turn["phase"] == "synthesis" else 350,
                "guidance": "Finish a complete, concise contribution within this budget. Prioritize the answer, substantive challenges and uncertainty; summarize large deliverables rather than starting an unfinished long document.",
            },
        }
        if turn["phase"] == "opening":
            payload["instructions"] = (
                "Give your own independent answer to the original question. State your proposal, key assumptions, supporting rationale and uncertainty. You have not seen peers' answers. Be concrete and concise; do not assume an engineering experiment has run."
            )
        else:
            baseline = [m for m in messages if m.get("phase") == "opening"]
            payload["shared_baseline"] = [
                {
                    "id": m["id"],
                    "reference": f"#{m['sequence']}",
                    "model": m["model"],
                    "name": m["name"],
                    "answer": m["content"] if chat["provider"] == "nebius_token_factory" else m["content"][:6000],
                }
                for m in baseline
            ]
            context_ids += [m["id"] for m in baseline]
            notes = [
                m for m in messages if m["role"] == "user" and m["id"] != opening["id"]
            ]
            if chat["provider"] != "nebius_token_factory":
                notes = notes[-2:]
            payload["director_notes"] = [
                {"id": m["id"], "reference": f"#{m['sequence']}", "text": m["content"]}
                for m in notes
            ]
            context_ids += [m["id"] for m in notes]
            history, size = [], 0
            for m in reversed(messages):
                if m.get("phase") not in ("debate", "synthesis"):
                    continue
                excerpt = m["content"] if chat["provider"] == "nebius_token_factory" else m["content"][:6000]
                if chat["provider"] != "nebius_token_factory" and size + len(excerpt) > 16000:
                    break
                history.insert(
                    0,
                    {
                        "id": m["id"],
                        "reference": f"#{m['sequence']}",
                        "name": m["name"],
                        "model": m["model"],
                        "round": m["round"],
                        "answer": excerpt,
                    },
                )
                context_ids.append(m["id"])
                size += len(excerpt)
            payload["discussion_so_far"] = history
            payload["context_policy"] = (
                "Opening answers form the shared reference baseline. All supplied public replies and user notes remain complete; Token Factory context fitting is checked against 262,144 tokens. Prior assessments are not independent evidence."
                if chat["provider"] == "nebius_token_factory" else "Opening answers form the shared reference baseline. Older long messages may be excerpted. Absence from this window is not evidence of agreement."
            )
            if turn["phase"] == "debate":
                payload["instructions"] = (
                    "Address the original question and latest director notes. Respond to specific named peers: challenge the strongest weak assumption, defend or revise your own position, and offer a better answer. Cite the visible message references such as #2 with the speaker's name. Avoid repeating the baseline. End with remaining disagreements. Do not agree merely to end the discussion; the director chooses its duration."
                )
            else:
                payload["instructions"] = (
                    "Write the final synthesis for the user. Answer the latest director request directly, using the original question as context. If the latest request asks for a number of approaches, provide that number as the main structure. Reconcile the strongest supported proposals, explain the recommended steps, and include an 'Unresolved disagreements and uncertainty' section. Attribute conflicting positions to their actual models. Explicitly disclose any unavailable members: their absence is not agreement and never invent their answers. Never claim unanimous agreement, external verification or measurements unless the supplied transcript establishes them. This is a generated synthesis for human review."
                )
        if turn["participant"].get("provider") == "groq":
            from .council_runtime import groq_discussion_context
            prompt, visible_ids = groq_discussion_context(payload, chat.get("groq_context_max", 10500))
            return prompt, list(dict.fromkeys([opening["id"], *visible_ids]))
        return json.dumps(payload, ensure_ascii=False), list(dict.fromkeys(context_ids))

    def run_turn(self, job, stopped):
        cid = job["target_id"]
        from .answer_delivery import AnswerDelivery, enabled as answer_first
        delivery = AnswerDelivery(self)
        if delivery.reconcile(cid):
            return
        with self.store.tx() as c:
            chat = self.store.get(c, cid, "chat")
            from .execution_slots import opening_parallelism_allowed
            opening_parallelism_allowed(chat.get('execution_descriptor', {}))
            if chat.get('execution_descriptor_hash') and digest(chat['execution_descriptor']) != chat['execution_descriptor_hash']:
                raise DomainError('Saved execution descriptor changed; execution refused', 422)
            if chat["status"] != "running":
                return
            from .council_web_search import apply_pending
            apply_pending(self, c, chat)
            if len(self.active_members(chat)) < 2 and not chat.get("requested_finish"):
                raise FreeProviderError(
                    "Free providers cannot currently supply two council participants. Saved replies remain available; you can retry later or explicitly request a partial synthesis.",
                    kind="council_unavailable",
                )
            if (
                digest(chat["protocol"]) != chat["protocol_hash"]
                or chat["participants"] != chat["protocol"]["participants"]
                or chat["original_prompt"] != chat["protocol"]["prompt"]
                or chat["provider"] != chat["protocol"]["provider"]
                or chat.get("mode", "discussion")
                != chat["protocol"].get("mode", "discussion")
            ):
                raise DomainError(
                    "Frozen council configuration changed; execution refused", 422
                )
            messages = self.messages(c, chat)
            turn = self.next_turn(chat, messages, c)
            if not turn:
                chat.update(status="completed", active_turn=None)
                self.runtime.release_capacity(c, chat["mission_id"], "Completed")
                self.store.put(c, "chat", chat)
                return
            self.runtime.prepare_turn(c, chat, turn)
            turn = self.runtime.effective_turn(c, chat, turn)
            final_hold = None
            if answer_first(chat):
                from .answer_budget import finishing_hold
                final_hold = finishing_hold(self, c, chat, turn)
            prompt, context_ids = self.prompt(chat, messages, turn, c)
            review_input_revision = (
                self.review.record(c, chat)["revision"]
                if chat.get("mode") == "reviewed"
                else None
            )
            chat["active_turn"] = {
                "job_id": job["id"],
                "phase": turn["phase"],
                "round": turn["round"],
                "model": turn["participant"]["model"],
                "name": turn["participant"]["name"],
                "thinking_level": chat.get("thinking_level", "balanced") if chat["provider"] == "nebius_token_factory" else None,
            }
            self.store.put(c, "chat", chat)
            self.store.event(
                c,
                chat["mission_id"],
                "chat.turn_started",
                {"chat_id": cid, **chat["active_turn"]},
            )
            if answer_first(chat):
                intent = {"id": "intent_" + digest([cid, turn["key"], job["id"]])[:28], "mission_id": chat["mission_id"],
                          "chat_id": cid, "turn": turn, "prompt": prompt, "context_ids": context_ids,
                          "input_revision": review_input_revision, "protocol_hash": chat["protocol_hash"],
                          "saved_chat_status": chat["status"], "created_at": now()}
                self.store.put(c, "answer_intent", intent)

        def cancelled():
            if stopped():
                return True
            with self.store.tx() as c:
                return self.store.get(c, cid, "chat")["status"] != "running"

        def stream_cancelled():
            if stopped():
                return True
            with self.store.tx() as c:
                return self.store.get(c, cid, "chat")["status"] not in ("running", "paused")

        call = None
        if chat["provider"] == "fixture":
            if chat.get("mode") == "reviewed":
                with self.store.tx() as c:
                    content = self.review.demo(c, chat, messages, turn)
            else:
                content = self.demo_answer(chat, messages, turn)
        else:
            participant = turn["participant"]
            provider = (
                self.research.direct_provider
                if chat["provider"] == "direct_council"
                else OpenRouterFreeProvider(
                    self.store,
                    self.settings,
                    self.research.artifacts,
                    model=participant["model"],
                )
                if chat["provider"] == "openrouter_free"
                else self.research.provider
            )
            caller = self.research.research_execution.call if chat['provider'] in ('direct_council', 'nebius_token_factory') and chat.get('execution_descriptor') else provider.call
            content, call = caller(
                chat["mission_id"],
                prompt,
                self.output_limit(chat, turn),
                model=participant["model"],
                purpose=f"chat:{cid}:{turn['key']}",
                cancelled=cancelled,
                **({"stream_cancelled": stream_cancelled} if chat["provider"] == "nebius_token_factory" else {}),
                plain_text=True,
                **({"chat": chat, "turn": turn} if caller == self.research.research_execution.call else {}),
                **({"fallback_for": participant.get("replacement_for")} if chat["provider"] == "direct_council" else {}),
                **({"recovery_from": chat["pending_output_recovery"]["call_id"]} if chat["provider"] == "nebius_token_factory" and chat.get("pending_output_recovery") else {}),
                **({"hold_id": final_hold["hold_id"]} if final_hold and turn["phase"] == "synthesis" else {}),
                **({"generation": token_factory_profile(self.settings, turn, recovery=bool(chat.get("pending_output_recovery")), thinking_level=chat.get("thinking_level", "balanced"))} if chat["provider"] == "nebius_token_factory" else {}),
            )
        if not content.strip():
            raise DomainError("Model returned an empty council answer", 502)
        content = self.research.artifacts.redact(content)
        ready = turn["phase"] == "debate" and READY in content
        content = content.replace(READY, "").strip()
        if answer_first(chat):
            item = delivery.commit(cid, turn, content, call, prompt, context_ids, review_input_revision)
            delivery.annotate(item["id"])
            return
        with self.store.tx() as c:
            current = self.store.get(c, cid, "chat")
            message_id = uid("message")
            outdated = False
            if chat.get("mode") == "reviewed":
                outdated = (
                    self.review.record(c, current)["revision"] != review_input_revision
                )
                from .review_delivery import admit_deliverable
                content = admit_deliverable(self, c, current, turn, content, message_id)
                if outdated:
                    review = self.review.record(c, current)
                    review.update(stale=True, synthesis_stale=True)
                    self.store.put(c, "chat_review", review)
            review_incomplete = bool(current.get("mode") == "reviewed"
                                     and self.review.record(c, current).get("delivery_degraded"))
            message = self.message(
                c,
                current,
                id=message_id,
                role="assistant",
                content=content,
                phase=turn["phase"],
                round=turn["round"],
                participant_id=turn["participant"]["id"],
                name=turn["participant"]["name"],
                model=turn["participant"]["model"],
                turn_key=turn["key"],
                review_cycle=turn.get("cycle"),
                outdated_context=outdated,
                ready=ready,
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
                call_id=call["id"] if call else None,
                recovery_from_call_id=call.get("recovery_from_call_id") if call else None,
                source="fixture" if call is None else "model_api",
                provider=turn["participant"].get("provider", current["provider"]),
                actual_model=turn["participant"].get(
                    "actual_model", turn["participant"]["model"]
                ),
                replacement_for=turn["participant"].get("replacement_for"),
                replacement_name=turn["participant"].get("replacement_name"),
                review_incomplete=review_incomplete,
                partial=bool(
                    current.get("requested_finish")
                    or current.get("unavailable_members")
                    or review_incomplete
                )
                if turn["phase"] == "synthesis"
                else False,
            )
            current.update(
                active_turn=None,
                retry_wait=None,
                error=None,
                revision=current["revision"] + 1,
            )
            if turn["phase"] == "synthesis":
                current["final_message_id"] = message["id"]
            if current["status"] == "running":
                if self.next_turn(current, self.messages(c, current), c):
                    self.research.enqueue(c, "chat", current)
                else:
                    current["status"] = "completed"
                    self.runtime.release_capacity(c, current["mission_id"], "Completed")
                    step = self.store.get(c, current["step_id"], "step")
                    step["status"] = "decision_ready"
                    self.store.put(c, "step", step)
            self.store.put(c, "chat", current)
            self.store.event(
                c,
                current["mission_id"],
                "chat.turn_completed",
                {
                    "chat_id": cid,
                    "message_id": message["id"],
                    "status": current["status"],
                },
            )

    def handle_failure(self, job, error):
        from .answer_delivery import AnswerDelivery
        if AnswerDelivery(self).failed_turn(job, error):
            return True
        if not isinstance(error, FreeProviderError):
            return False
        with self.store.tx() as c:
            chat = self.store.get(c, job["target_id"], "chat")
            if chat["provider"] not in ("openrouter_free", "direct_council"):
                return False
            c.execute(
                "UPDATE jobs SET state='failed',body=? WHERE id=?",
                (json.dumps({"error": error.message, "kind": error.kind}), job["id"]),
            )
            if chat["status"] in ("paused", "cancelled"):
                chat.update(active_turn=None, error=error.message)
                self.store.put(c, "chat", chat)
                return True
            turn = self.next_turn(chat, self.messages(c, chat), c)
            if not turn:
                return False
            if chat.get("model_overrides", {}).get(turn["participant"]["id"]):
                turn = self.runtime.effective_turn(c, chat, turn)
            counts = chat.setdefault("retry_counts", {})
            used = chat.get("retry_used", 0)
            count = counts.get(turn["key"], 0)
            capacity = (
                self.research.direct_provider
                if chat["provider"] == "direct_council"
                else self.research.free_provider
            ).capacity(c, chat["mission_id"], required=0)
            retryable = error.retryable
            switched = False
            role_reassigned = False
            if chat["provider"] == "direct_council":
                eligible = error.kind in ("request_too_large", "provider_temporary", "platform_rate_limit", "network_ambiguous", "model_unavailable", "output_incomplete")
                if eligible and turn["participant"].get("provider") == "groq":
                    if error.kind == "output_incomplete":
                        chat["groq_output_limit"] = 4096
                    if error.kind == "request_too_large":
                        chat["groq_context_max"] = 7000
                    failures = self.runtime.failures(c, chat, turn)
                    if len(failures) >= 2:
                        switched = self.runtime.fallback(c, chat, turn, error.message)
                    # 413 gets one smaller discussion retry, never an unbounded loop.
                    retryable = retryable or (error.kind == "request_too_large" and len(failures) < 2)
                    if switched:
                        turn = self.runtime.effective_turn(c, chat, turn)
                if not switched:
                    reassigned = self.runtime.reassign_unavailable_role(c, chat, turn, error, count, used)
                    if reassigned:
                        turn, switched, retryable = reassigned, True, True
                        role_reassigned = True
            can_retry = (
                (switched or (retryable and count < RETRIES_PER_TURN
                and used - chat.get("retry_window_start", 0) < RETRY_ALLOWANCE))
                and capacity["remaining_calls"]
                >= self.remaining(chat, self.messages(c, chat), c)
                and capacity["daily_remaining"]
                >= self.remaining(chat, self.messages(c, chat), c)
                and (error.retry_after <= 3600 or role_reassigned)
            )
            if chat["protocol"]["version"] in ("reviewed_v3", "reviewed_v4"):
                can_retry = can_retry and count < RETRIES_PER_TURN and used - chat.get("retry_window_start", 0) < RETRY_ALLOWANCE and self.runtime.recovery_usage(c, chat) < 3
            if can_retry:
                count += 1
                counts[turn["key"]] = count
                chat["retry_used"] = used + 1
                delay = 1 if role_reassigned else max(error.retry_after, 20 * 2 ** (count - 1))
                due = (datetime.now(UTC) + timedelta(seconds=delay + 1)).isoformat()
                chat.update(
                    status="waiting",
                    active_turn=None,
                    error=None,
                    retry_wait={
                        "name": turn["participant"]["name"],
                        "model": turn["participant"]["model"],
                        "attempt": count,
                        "maximum": RETRIES_PER_TURN,
                        "not_before": due,
                        "reason": error.message,
                        "kind": error.kind,
                    },
                )
                jid = self.research.enqueue(c, "chat", chat)
                c.execute(
                    "UPDATE jobs SET body=? WHERE id=?",
                    (json.dumps({"not_before": due}), jid),
                )
                event = "chat.retry_scheduled"
            else:
                skippable = error.kind in (
                    "upstream_capacity",
                    "provider_temporary",
                    "network_ambiguous",
                    "model_unavailable",
                )
                if chat["provider"] == "direct_council" and error.kind in (
                    "platform_rate_limit",
                    "credential",
                    "access",
                    "account",
                    "output_incomplete",
                    "request_too_large",
                ):
                    skippable = True
                if skippable:
                    member = turn["participant"]
                    chat.setdefault("unavailable_members", {})[member["id"]] = {
                        **member,
                        "reason": error.message,
                        "kind": error.kind,
                        "recorded_at": now(),
                        "phase": turn["phase"],
                        "turn_key": turn["key"],
                    }
                review_phase_missing = chat.get("mode") == "reviewed" and turn[
                    "phase"
                ] not in ("opening", "repair")
                if chat.get("mode") == "reviewed" and skippable:
                    review = self.review.record(c, chat)
                    review.setdefault("partial_reasons", []).append(
                        turn["phase"] + " unavailable: " + turn["participant"]["name"]
                    )
                    if not review_phase_missing:
                        review.setdefault("skipped_keys", []).append(turn["key"])
                    review["revision"] += 1
                    self.store.put(c, "chat_review", review)
                if (
                    skippable
                    and len(self.active_members(chat)) >= 2
                    and not review_phase_missing
                ):
                    chat.update(
                        status="running", active_turn=None, retry_wait=None, error=None
                    )
                    self.research.enqueue(c, "chat", chat)
                    event = "chat.member_unavailable"
                else:
                    message = error.message
                    if skippable:
                        message = (
                            "A required review phase is unavailable. Reassign it to a selected available member, retry explicitly, or request a partial synthesis."
                            if review_phase_missing
                            else "Free providers cannot currently supply two council participants. Your saved answers are intact; retry later or explicitly request a partial synthesis."
                        )
                    chat.update(
                        status="unavailable",
                        active_turn=None,
                        retry_wait=None,
                        error=message,
                    )
                    step = self.store.get(c, chat["step_id"], "step")
                    step["status"] = "blocked"
                    self.store.put(c, "step", step)
                    event = "chat.unavailable"
            if chat["status"] in ("unavailable", "failed", "cancelled"):
                self.runtime.release_capacity(c, chat["mission_id"], chat["status"])
            chat["revision"] += 1
            self.store.put(c, "chat", chat)
            self.store.event(
                c,
                chat["mission_id"],
                event,
                {
                    "chat_id": chat["id"],
                    "kind": error.kind,
                    "model": turn["participant"]["model"],
                },
            )
        return True

    def demo_answer(self, chat, messages, turn):
        name = turn["participant"]["name"]
        if turn["phase"] == "opening":
            angle = {
                "demo/analyst": "Define the objective and a small reference case before choosing a solution.",
                "demo/critic": "Challenge the assumptions: what evidence would show that the proposed solution fails?",
                "demo/builder": "Build the smallest observable implementation, then check it against the reference case.",
            }[turn["participant"]["model"]]
            return f"**Synthetic demo answer — {name}**\n\nFor your question, “{chat['original_prompt']}”, my initial position is:\n\n{angle}\n\nThis is scripted demonstration text, not a live model response."
        if turn["phase"] == "debate":
            peers = ", ".join(
                p["name"]
                for p in chat["participants"]
                if p["id"] != turn["participant"]["id"]
            )
            return f"**Synthetic debate turn — round {turn['round']}**\n\nI have now seen {peers}'s opening positions and the preceding discussion. A baseline is useful, but it does not establish that the implementation is correct.\n\nI revise the recommendation: define one falsifiable acceptance case, build the smallest version, and keep a negative result visible.\n\n**Still unresolved:** the best solution to the actual question requires real model reasoning and evidence. This turn is a scripted demo."
        return "## Final synthesis — synthetic demo\n\nThe council sequence is now visible: separate opening answers, a shared reference baseline, sequential challenges and revisions, and this final synthesis.\n\nFor a real answer to your question, start a council with the free OpenRouter models or a verified Token Factory account.\n\n### Unresolved disagreements and uncertainty\n\nNo real model reasoning or experiments were performed in this demo. The original question remains unverified."
