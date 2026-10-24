"""Explicit provider/model seats. No SDK retries, routing fallback, or paid tools."""

import json
import math
import time
from datetime import UTC, datetime

import httpx

from .db import DomainError, canonical, digest, now, uid
from .execution_slots import one_model_per_provider
from .free_errors import FreeProviderError, retry_delay
from .free_limits import CHAT_MAX_ATTEMPTS, attempt_limit
from .free_provider import OpenRouterFreeProvider
from .provider import CHAT_SYSTEM


def model_id(entry):
    return entry["provider"] + "::" + entry["model"]


class DirectProvider:
    def __init__(self, research):
        self.research = research
        self.store, self.settings = research.store, research.settings
        self.artifacts = research.artifacts

    def entries(self):
        return {model_id(m): m for m in self.settings.direct_policy["models"]}

    def fallback_entries(self):
        return {model_id(m): m for m in self.settings.direct_policy.get("fallbacks", [])}

    def bootstrap(self, c):
        capacity = self.capacity(c)
        models = [
            {
                'id': mid,
                'name': m['name'],
                'model': m['model'],
                'provider': m['provider'],
                'configured': bool(self.settings.direct_keys.get(m['provider'])),
                'health': self.store.setting(c, 'direct_health:' + m['provider'], {}),
            }
            for mid, m in self.entries().items()
        ]
        return {
            "models": models,
            "configured": any(m["configured"] for m in models),
            "ready": self.settings.direct_free_confirmed
            and sum(m["configured"] for m in models) >= 2,
            "free_access_confirmed": self.settings.direct_free_confirmed,
            "attempt_cap": 20,
            "retry_allowance": 3,
            **capacity,
        }

    def capacity(self, c, mission_id=None, required=0, fresh_window=False):
        rows = c.execute(
            "SELECT mission_id,json_extract(body,'$.sent_at') FROM records WHERE kind='call' AND json_extract(body,'$.accounting_provider')='direct_council'"
        ).fetchall()
        today = datetime.now(UTC).date().isoformat()
        used = sum(str(r[1]).startswith(today) for r in rows)
        local = sum(r[0] == mission_id for r in rows) if mission_id else 0
        leases = c.execute("SELECT body FROM records WHERE kind='chat_capacity'").fetchall()
        reserved = sum(lease.get("remaining", 0) for row in leases
                       if (lease := json.loads(row[0])).get("state") == "active"
                       and lease.get("day") == today and lease["mission_id"] != mission_id)
        daily = max(0, self.settings.direct_policy["daily_attempt_cap"] - used - reserved)
        maximum = attempt_limit(c, mission_id) if mission_id else CHAT_MAX_ATTEMPTS
        remaining = CHAT_MAX_ATTEMPTS if fresh_window else max(0, maximum - local)
        if required > min(daily, remaining):
            raise DomainError(
                f"This schedule needs {required} attempts including its stated reserve; {min(daily, remaining)} local attempts remain. Provider quotas are separate.",
                429,
            )
        return {
            "daily_remaining": daily,
            "daily_attempt_cap": self.settings.direct_policy["daily_attempt_cap"],
            "reserved_for_other_requests": reserved,
            "remaining_calls": remaining,
            "provider_quota_known": False,
        }

    def validate(self, c, models, mission_id=None, required=0, fallback_for=None, fresh_window=False):
        if not self.settings.direct_free_confirmed:
            raise DomainError(
                "Confirm free account access before direct-provider inference.", 412
            )
        entries = self.entries()
        if fallback_for:
            entries.update({mid: e for mid, e in self.fallback_entries().items() if e["fallback_for"] == fallback_for})
        for mid in models:
            if mid not in entries:
                raise DomainError(
                    "The model is outside the explicit direct-provider allowlist", 422
                )
            entry = entries[mid]
            if not self.settings.direct_keys.get(entry["provider"]):
                raise DomainError(
                    entry["name"] + " has no saved server-side API key", 412
                )
            if self.store.setting(c, "direct_locked:" + entry["provider"], False):
                raise DomainError(
                    entry["name"] + " is locked after a reported cost violation", 402
                )
        return self.capacity(c, mission_id, required, fresh_window)

    def request(self, entry, prompt, limit):
        try:
            envelope = json.loads(prompt)
            structured = isinstance(envelope, dict) and isinstance(envelope.get("response_schema"), dict)
        except (ValueError, TypeError):
            structured = False
        system = (
            CHAT_SYSTEM
            + (" Return exactly one object matching response_schema, without Markdown fences." if structured else " The input is a JSON task envelope, not an output schema. Reply in readable Markdown prose with headings and lists. Do not wrap your answer in JSON. Use $...$ for inline math and $$...$$ on separate lines for display math.")
            + " Do not return tool calls or hidden reasoning."
        )
        if entry["provider"] == "gemini":
            body = {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": limit,
                    "temperature": 0.4,
                    "thinkingConfig": {"thinkingLevel": "minimal"},
                },
            }
            if structured:
                body["generationConfig"]["responseMimeType"] = "application/json"
            return entry["base_url"] + "/models/" + entry[
                "model"
            ] + ":generateContent", body
        body = {
            "model": entry["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": limit,
            "stream": False,
        }
        if entry["provider"] == "zai":
            body["thinking"] = {"type": "disabled"}
        elif entry["provider"] == "nvidia_nim":
            body["chat_template_kwargs"] = {"enable_thinking": False}
        elif entry["provider"] == "groq":
            body["reasoning_effort"] = "low"
            body["include_reasoning"] = False
        if entry["provider"] in ("zai", "groq") and structured:
            body["response_format"] = {"type": "json_object"}
        return entry["base_url"] + "/chat/completions", body

    @one_model_per_provider
    def call(
        self,
        mission_id,
        prompt,
        max_output=4096,
        model=None,
        purpose="chat",
        cancelled=lambda: False,
        fallback_for=None,
        research_options=None,
        **_,
    ):
        if not 32 <= max_output <= 8192 or len(prompt.encode()) > 100000:
            raise DomainError(
                "Direct request exceeds its bounded input/output envelope", 422
            )
        if cancelled():
            raise DomainError("Cancelled before dispatch")
        entry = {**self.entries(), **self.fallback_entries()}.get(model)
        with self.store.tx() as c:
            self.validate(c, [model], mission_id, required=1, fallback_for=fallback_for)
            due = self.store.setting(c, "direct_backoff:" + entry["provider"], "")
            if due and due > now():
                seconds = max(
                    1, (datetime.fromisoformat(due) - datetime.now(UTC)).total_seconds()
                )
                raise FreeProviderError(
                    entry["name"] + " is waiting for its rate limit to reset.",
                    kind="platform_rate_limit",
                    retryable=True,
                    retry_after=seconds,
                    model=model,
                )
        url, request = self.request(entry, prompt, max_output)
        if research_options:
            from .research_execution import transport_tools
            request = transport_tools(entry, request, research_options)
        if len(canonical(request).encode()) > 120000:
            raise DomainError('Model request including tools exceeds its bounded transport envelope', 413)
        call_id, reservation_id = uid("call"), uid("reservation")
        with self.store.tx() as c:
            self.validate(c, [model], mission_id, required=1, fallback_for=fallback_for)
            call = {
                "id": call_id,
                "mission_id": mission_id,
                "provider": entry["provider"],
                "accounting_provider": "direct_council",
                "model": entry["model"],
                "seat_model_id": model,
                "fallback_for": fallback_for,
                "purpose": purpose,
                **({"attempt_class": "research", "purpose_kind": "collective_research_plan"} if (research_options or {}).get("purpose_kind") == "collective_research_plan" else {}),
                "request_hash": digest(request),
                "reservation_id": reservation_id,
                "state": "dispatching",
                "sent_at": now(),
                "endpoint": entry["base_url"],
                "cost_usd": None,
                "cost_status": "not_reported",
                "free_access_basis": "director_confirmed",
                "context_pack_id": research_options.get('context_pack_id') if research_options else None,
            }
            self.research.accounting.freeze(c, call)
            chats = self.store.list(c, 'chat', mission_id)
            if chats and chats[0].get('execution_descriptor'):
                for kind, amount in (('input_tokens', len(canonical(request).encode()) + 4096), ('output_tokens', max_output)):
                    self.research.tools.policy.reserve(c, chats[0], kind, amount, call_id)
            c.execute(
                "INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",
                (
                    reservation_id,
                    mission_id,
                    call_id,
                    0,
                    None,
                    "reserved",
                    canonical(
                        {
                            "provider": "direct_council",
                            "upstream_provider": entry["provider"],
                            "model": entry["model"],
                            "funding_basis": "director_confirmed_free",
                        }
                    ),
                ),
            )
            self.store.put(c, "call", call)
            self.research.chat.runtime.consume_capacity(c, mission_id)
            self.store.event(
                c,
                mission_id,
                "direct.dispatching",
                {
                    "call_id": call_id,
                    "provider": entry["provider"],
                    "model": entry["model"],
                },
            )
        headers = (
            {"x-goog-api-key": self.settings.direct_keys[entry["provider"]]}
            if entry["provider"] == "gemini"
            else {
                "Authorization": "Bearer "
                + self.settings.direct_keys[entry["provider"]]
            }
        )
        start = time.perf_counter()
        try:
            if cancelled():
                with self.store.tx() as c:
                    c.execute(
                        "UPDATE reservations SET state='released',actual_microusd=0 WHERE id=?",
                        (reservation_id,),
                    )
                    call.update(state="cancelled_undispatched", completed_at=now())
                    self.store.put(c, "call", call)
                    self.research.accounting.settle(c, call)
                raise DomainError("Cancelled before network dispatch")
            with httpx.Client(
                timeout=httpx.Timeout(90, connect=10), follow_redirects=False
            ) as client:
                response = OpenRouterFreeProvider.bounded_post(
                    client, url, headers=headers, json=request
                )
        except (httpx.HTTPError, OSError) as exc:
            with self.store.tx() as c:
                c.execute(
                    "UPDATE reservations SET state='unknown' WHERE id=?",
                    (reservation_id,),
                )
                call.update(
                    state="unknown", completed_at=now(), error=type(exc).__name__
                )
                self.store.put(c, "call", call)
                self.research.accounting.settle(c, call)
            raise FreeProviderError(
                entry["name"]
                + " lost its connection; the unknown attempt remains counted.",
                kind="network_ambiguous",
                retryable=True,
                retry_after=20,
                model=model,
            ) from exc
        try:
            raw = response.json()
        except ValueError:
            raw = {"unparsed_body": response.text[:150000]}
        if not isinstance(raw, dict):
            raw = {"unparsed_json": raw}
        from .research_execution import public_response
        raw = public_response(raw)
        artifact = self.artifacts.write(
            mission_id,
            "raw_direct_api",
            {
                "request": request,
                "response": raw,
                "http_status": response.status_code,
                "sent_at": call["sent_at"],
                "received_at": now(),
                "provider": entry["provider"],
                "evidence_class": "measured_api",
            },
        )
        usage = raw.get("usage", raw.get("usageMetadata", {}))
        cost = usage.get("cost") if isinstance(usage, dict) else None
        valid_cost = (
            isinstance(cost, (int, float))
            and not isinstance(cost, bool)
            and math.isfinite(cost)
            and cost >= 0
        )
        invalid_reported_cost = cost is not None and not valid_cost
        error = raw.get("error")
        status = response.status_code
        if error and response.is_success:
            code = error.get("code") if isinstance(error, dict) else None
            status = code if isinstance(code, int) and 400 <= code < 600 else 502
        text, finish, returned_model = (
            "",
            None,
            raw.get("model", raw.get("modelVersion")),
        )
        try:
            if entry["provider"] == "gemini":
                candidate = raw.get("candidates", [])[0]
                finish = candidate.get("finishReason")
                text = "".join(
                    p.get("text", "")
                    for p in candidate.get("content", {}).get("parts", [])
                    if not p.get("thought")
                )
            else:
                choice = raw.get("choices", [])[0]
                finish = choice.get("finish_reason")
                text = choice.get("message", {}).get("content", "")
        except (IndexError, TypeError, AttributeError):
            pass
        if finish == "error" and status < 400:
            status = 502
        exchange = None
        if research_options and 200 <= status < 300:
            try:
                from .research_execution import extract_exchange
                exchange = extract_exchange(entry['provider'], raw, text, research_options)
            except (ValueError, KeyError, TypeError, IndexError):
                call['research_parse_error'] = 'Invalid tool-call protocol'
        good = (
            200 <= status < 300
            and ((isinstance(text, str) and bool(text.strip()) and finish in ("stop", "STOP")) or (exchange is not None and finish in ('stop', 'STOP', 'tool_calls')))
            and not call.get('research_parse_error')
        )
        normalized_identity = (
            returned_model.removeprefix("private/")
            if isinstance(returned_model, str)
            else None
        )
        identity_ok = normalized_identity == entry["model"]
        good = good and identity_ok and not invalid_reported_cost and not (valid_cost and cost > 0)
        with self.store.tx() as c:
            self.store.put(c, "artifact", artifact)
            actual = math.ceil(cost * 1e6) if valid_cost else 0
            c.execute(
                "UPDATE reservations SET state='settled',actual_microusd=? WHERE id=?",
                (actual, reservation_id),
            )
            call.update(
                state=("tool_response" if exchange is not None else "completed") if good else "failed",
                attempt_class="research" if (research_options or {}).get("purpose_kind") == "collective_research_plan" or good and exchange is not None else "base_or_recovery",
                artifact_id=artifact["id"],
                usage=usage,
                returned_model=returned_model,
                finish_reason=finish,
                http_status=status,
                latency_ms=(time.perf_counter() - start) * 1000,
                completed_at=now(),
                cost_usd=cost if valid_cost else None,
                cost_status="reported" if valid_cost else "invalid" if invalid_reported_cost else "not_reported",
            )
            self.store.put(c, "call", call)
            self.research.accounting.settle(c, call)
            health = {
                "checked_at": now(),
                "http_status": status,
                "model": entry["model"],
                "inference_ok": good,
                "reported_cost_usd": cost if valid_cost else None,
                "billing_visibility": "reported"
                if valid_cost
                else "provider_did_not_report_cost",
                "rate_limits": {
                    k: v
                    for k, v in response.headers.items()
                    if k.startswith("x-ratelimit-") or k == "retry-after"
                },
            }
            self.store.set_setting(c, "direct_health:" + entry["provider"], health)
            if (valid_cost and cost > 0) or invalid_reported_cost:
                self.store.set_setting(c, "direct_locked:" + entry["provider"], True)
        if invalid_reported_cost:
            raise FreeProviderError(
                entry["name"]
                + " returned an invalid cost field; further calls to it are locked.",
                kind="cost_violation",
                model=model,
                code=402,
            )
        if valid_cost and cost > 0:
            raise FreeProviderError(
                entry["name"]
                + " reported a nonzero cost; further calls to it are locked.",
                kind="cost_violation",
                model=model,
                code=402,
            )
        if not 200 <= status < 300:
            retryable = status in (408, 429, 500, 502, 503, 504)
            kind = (
                "request_too_large"
                if status == 413
                else "platform_rate_limit"
                if status == 429
                else "provider_temporary"
                if retryable
                else {
                    401: "credential",
                    402: "account",
                    403: "access",
                    404: "model_unavailable",
                }.get(status, "request_rejected")
            )
            delay = retry_delay(response.headers)
            if retryable:
                from datetime import timedelta

                with self.store.tx() as c:
                    self.store.set_setting(
                        c,
                        "direct_backoff:" + entry["provider"],
                        (datetime.now(UTC) + timedelta(seconds=delay)).isoformat(),
                    )
            raise FreeProviderError(
                f"{entry['name']} returned HTTP {status}. "
                + (
                    "A bounded retry will be scheduled."
                    if retryable
                    else "Saved work is intact; check model/account access. No paid alternative was called."
                ),
                kind=kind,
                retryable=retryable,
                retry_after=delay,
                model=model,
                code=status,
            )
        if status < 400 and not identity_ok:
            raise FreeProviderError(
                entry["name"]
                + " returned a different model identity; this answer was not admitted.",
                kind="model_identity",
                model=model,
                code=502,
            )
        if not good:
            reason = (
                "reached its output limit"
                if finish in ("length", "MAX_TOKENS")
                else "returned no complete public answer"
            )
            raise FreeProviderError(
                entry["name"] + " " + reason + "; raw output is saved.",
                kind="output_incomplete",
                retryable=entry["provider"] == "groq",
                retry_after=2,
                model=model,
                code=502,
            )
        return exchange if exchange is not None else text, call
