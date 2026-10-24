"""Pinned free-only OpenRouter calls, separate from Token Factory authorization."""

import json
import math
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

import httpx

from .budget import micro
from .contracts import CrossReview, Submission
from .db import DomainError, canonical, digest, now, uid
from .free_errors import FreeProviderError, response_error
from .free_limits import DAILY_ATTEMPTS, attempt_limit
from .provider import CHAT_SYSTEM, Provider

BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
FREE_MODELS = (
    MODEL,
    "nvidia/nemotron-3.5-super-vl:free",
    "google/gemma-4-31b-it:free",
    "xingchen-agi/xing4.0-29b-a4b:free",
    "nvidia/nemotron-3.5-lightning:free",
)
CHAT_MODELS = (
    MODEL,
    "xingchen-agi/xing4.0-29b-a4b:free",
    "nvidia/nemotron-3.5-lightning:free",
    "google/gemma-4-31b-it:free",
)


def zero_priced(model):
    prices = model.get("pricing", {})
    try:
        return (
            model.get("id") in FREE_MODELS
            and {"prompt", "completion"} <= prices.keys()
            and all(
                Decimal(str(v)).is_finite() and Decimal(str(v)) == 0
                for v in prices.values()
            )
        )
    except (InvalidOperation, ValueError, TypeError):
        return False


class OpenRouterFreeProvider:
    provider_id = "openrouter_free"
    base_url = BASE_URL

    @staticmethod
    def bounded_post(client, url, **kwargs):
        started = time.monotonic()
        # OpenRouter can send whitespace keep-alives during non-streaming inference.
        # A per-read timeout alone never ends that response; inspect total elapsed time too.
        with client.stream("POST", url, **kwargs) as response:
            body = bytearray()
            for chunk in response.iter_bytes():
                if time.monotonic() - started > 120:
                    raise httpx.ReadTimeout(
                        "Free response exceeded the response deadline",
                        request=response.request,
                    )
                body.extend(chunk)
                if len(body) > 1048576:
                    raise httpx.ProtocolError(
                        "Free response exceeded the response size limit",
                        request=response.request,
                    )
            headers = {
                k: v
                for k, v in response.headers.items()
                if k.lower()
                not in ("content-encoding", "content-length", "transfer-encoding")
            }
            return httpx.Response(
                response.status_code,
                headers=headers,
                content=bytes(body),
                request=response.request,
            )

    def __init__(
        self, store, settings, artifacts, progress=lambda message: None, model=MODEL
    ):
        if model not in FREE_MODELS:
            raise DomainError(
                "Only explicitly allowed free variants can be tested", 412
            )
        self.store, self.settings, self.artifacts = store, settings, artifacts
        self.progress = progress
        self.model = model

    def choose(self, c=None, check_backoff=True):
        if not self.settings.openrouter_enabled:
            raise DomainError("OpenRouter is disabled; historical evidence remains readable.", 412)
        if not self.settings.openrouter_api_key:
            raise DomainError("OPENROUTER_API_KEY is missing", 412)
        if c is None:
            with self.store.tx() as connection:
                return self.choose(connection, check_backoff)
        if self.store.setting(c, "openrouter_free_locked", False):
            raise DomainError(
                "Free dispatch is locked after a cost or identity anomaly", 412
            )
        backoff = self.store.setting(c, "openrouter_free_backoff", None)
        scoped = self.store.setting(c, "openrouter_model_backoff", {}).get(self.model)
        backoff = max(filter(None, (backoff, scoped)), default=None)
        if (
            check_backoff
            and backoff
            and datetime.fromisoformat(backoff) > datetime.now(UTC)
        ):
            raise FreeProviderError(
                "The free provider's retry wait has not elapsed.",
                kind="upstream_capacity",
                retryable=True,
                model=self.model,
                retry_after=(
                    datetime.fromisoformat(backoff) - datetime.now(UTC)
                ).total_seconds(),
                code=429,
            )
        return self.model

    def capacity(self, c, mission_id=None, required=1):
        where = "json_extract(body,'$.provider')='openrouter_free'"
        used = c.execute(
            "SELECT COUNT(*) FROM reservations WHERE " + where + " AND mission_id=?",
            (mission_id,),
        ).fetchone()[0]
        today = datetime.now(UTC).date().isoformat()
        daily = c.execute(
            "SELECT COUNT(*) FROM reservations WHERE "
            + where
            + " AND json_extract(body,'$.catalog_checked_at')>=?",
            (today,),
        ).fetchone()[0]
        maximum = attempt_limit(c, mission_id)
        if required > max(0, maximum - used) or required > max(
            0, DAILY_ATTEMPTS - daily
        ):
            raise FreeProviderError(
                f"The local free-request allowance cannot cover this work: {maximum - used} conversation attempts and {DAILY_ATTEMPTS - daily} workspace requests remain today. Saved answers are intact.",
                kind="local_allowance",
                code=429,
            )
        return {
            "mission_attempts": used,
            "attempt_cap": maximum,
            "remaining_calls": max(0, maximum - used),
            "daily_attempts": daily,
            "daily_remaining": max(0, DAILY_ATTEMPTS - daily),
        }

    def cached_account(self, c):
        cached = self.store.setting(c, "openrouter_account_status", {})
        if cached.get("credential") != digest(self.settings.openrouter_api_key):
            return {"known": False, "remaining": None, "limit": None}
        return {k: v for k, v in cached.items() if k != "credential"}

    def account_status(self, force=False):
        with self.store.tx() as c:
            cached = self.store.setting(c, "openrouter_account_status", {})
        # A rotated key must never inherit another key's cached quota.
        credential = digest(self.settings.openrouter_api_key)
        if (
            not force
            and cached.get("credential") == credential
            and cached.get("checked_at")
            and datetime.fromisoformat(cached["checked_at"]).date()
            == datetime.now(UTC).date()
            and (
                datetime.now(UTC) - datetime.fromisoformat(cached["checked_at"])
            ).total_seconds()
            < 30
        ):
            return {k: v for k, v in cached.items() if k != "credential"}
        result = {"checked_at": now(), "known": False, "remaining": None, "limit": None}
        try:
            with httpx.Client(timeout=10, follow_redirects=False) as client:
                response = client.get(
                    BASE_URL + "/key",
                    headers={
                        "Authorization": "Bearer " + self.settings.openrouter_api_key
                    },
                )
            if response.status_code == 401:
                raise response_error(401, {}, {}, self.model)
            raw_status = response.json() if response.is_success else {}
            data = raw_status.get("data", {}) if isinstance(raw_status, dict) else {}
            quota = (
                data.get("free_model_daily_requests", {})
                if isinstance(data, dict)
                else {}
            )
            if isinstance(quota, dict) and all(
                isinstance(quota.get(k), int)
                and not isinstance(quota[k], bool)
                and quota[k] >= 0
                for k in ("used", "limit", "remaining")
            ):
                result.update(
                    known=True, **{k: quota[k] for k in ("used", "limit", "remaining")}
                )
        except (httpx.HTTPError, ValueError):
            pass
        with self.store.tx() as c:
            self.store.set_setting(
                c, "openrouter_account_status", {**result, "credential": credential}
            )
        return result

    def check_account(self, required=1):
        status = self.account_status()
        if status["known"] and status["remaining"] < required:
            raise FreeProviderError(
                f"OpenRouter has {status['remaining']} free requests remaining today; this work needs at least {required}. Wait for the daily reset. Shared-provider capacity is separate from this quota.",
                kind="daily_quota",
                code=429,
            )
        return status

    def schedule_hold(self, *args, **kwargs):
        raise DomainError("The free adapter does not run cost benchmark schedules", 412)

    def request(self, prompt, max_output, model):
        if model != self.model:
            raise DomainError("Only the pinned free model is allowed", 412)
        request = Provider.request(self, prompt, max_output, model)
        request["max_tokens"] = request.pop("max_completion_tokens")
        request.update(
            provider={
                "allow_fallbacks": False,
                "require_parameters": True,
                "max_price": {"prompt": 0, "completion": 0, "request": 0},
            },
            response_format={"type": "json_object"},
            reasoning={"enabled": False, "exclude": True},
        )
        try:
            payload = json.loads(prompt)
        except (ValueError, TypeError):
            payload = {}
        if isinstance(payload, dict):
            for contract in (Submission, CrossReview):
                if payload.get("output_schema") == contract.model_json_schema():
                    schema = contract.model_json_schema()
                    schema["required"] = list(schema["properties"])
                    request["response_format"] = {
                        "type": "json_schema",
                        "json_schema": {
                            "name": contract.__name__,
                            "strict": True,
                            "schema": schema,
                        },
                    }
                    break
        return request

    def call(
        self,
        mission_id,
        prompt,
        max_output=2048,
        model=None,
        purpose="research",
        cancelled=lambda: False,
        hold_id=None,
        plain_text=False,
    ):
        model = model or self.choose()
        self.choose()  # Require the credential even when a pinned model is supplied.
        request = self.request(prompt, max_output, model)
        if plain_text:
            request.pop("response_format", None)
            request["messages"][0]["content"] = CHAT_SYSTEM
            self.check_account()
        if hold_id or max_output > 4096 or max_output < 1:
            raise DomainError("Unsupported smoke-test request bounds", 412)
        if cancelled():
            raise DomainError("Cancelled before dispatch")
        with self.store.tx() as c:
            self.choose(c)
            self.capacity(c, mission_id)
            last = self.store.setting(c, "openrouter_last_dispatch", None)
        if last:
            elapsed = (datetime.now(UTC) - datetime.fromisoformat(last)).total_seconds()
            # Pace dispatches, without retrying failed requests.
            remaining = max(0, 3.1 - elapsed)
            if remaining:
                time.sleep(remaining)
        with httpx.Client(
            timeout=httpx.Timeout(90, connect=10), follow_redirects=False
        ) as client:
            try:
                catalog = client.get(BASE_URL + "/models")
            except (httpx.HTTPError, OSError) as exc:
                raise FreeProviderError(
                    "The free-model catalog is temporarily unreachable; no inference was dispatched.",
                    kind="provider_temporary",
                    retryable=True,
                    retry_after=20,
                    model=model,
                ) from exc
            if not catalog.is_success:
                if catalog.status_code in (429, 500, 502, 503, 504):
                    raise response_error(
                        catalog.status_code, {}, catalog.headers, model
                    )
                raise DomainError("Free model catalog could not be verified", 412)
            entry = next(
                (x for x in catalog.json().get("data", []) if x.get("id") == model), {}
            )
            if not zero_priced(entry):
                raise DomainError(
                    "The pinned model is absent or no longer entirely zero priced", 412
                )
            if entry.get("reasoning", {}).get("mandatory", False):
                raise DomainError(
                    "The smoke model no longer supports disabling reasoning", 412
                )
            if cancelled():
                raise DomainError("Cancelled before dispatch")
            call_id, reservation_id = uid("call"), uid("reservation")
            with self.store.tx() as c:
                # Recheck within the transaction that commits the dispatch intent.
                self.choose(c)
                self.capacity(c, mission_id)
                sent_at = now()
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
                                "provider": "openrouter_free",
                                "model": model,
                                "pricing": entry["pricing"],
                                "catalog_checked_at": sent_at,
                            }
                        ),
                    ),
                )
                call = {
                    "id": call_id,
                    "mission_id": mission_id,
                    "provider": "openrouter_free",
                    "model": model,
                    "purpose": purpose,
                    "endpoint": BASE_URL,
                    "request_hash": digest(request),
                    "reservation_id": reservation_id,
                    "state": "dispatching",
                    "sent_at": sent_at,
                    "ttft_ms": None,
                }
                self.store.put(c, "call", call)
                self.store.set_setting(c, "openrouter_last_dispatch", sent_at)
                quota = self.store.setting(c, "openrouter_account_status", {})
                if quota.get("known"):
                    quota["remaining"] = max(0, quota["remaining"] - 1)
                    quota["used"] += 1
                    self.store.set_setting(c, "openrouter_account_status", quota)
                self.store.event(
                    c,
                    mission_id,
                    "free_test.dispatching",
                    {"call_id": call_id, "model": model},
                )
            self.progress("Dispatching " + purpose)
            started = time.perf_counter()
            if cancelled():
                with self.store.tx() as c:
                    c.execute(
                        "UPDATE reservations SET state='released',actual_microusd=0 WHERE id=?",
                        (reservation_id,),
                    )
                    call.update(state="cancelled_undispatched", completed_at=now())
                    self.store.put(c, "call", call)
                    self.store.event(
                        c,
                        mission_id,
                        "free_test.cancelled_undispatched",
                        {"call_id": call_id},
                    )
                raise DomainError("Cancelled before network dispatch; no request sent")
            try:
                response = self.bounded_post(
                    client,
                    BASE_URL + "/chat/completions",
                    headers={
                        "Authorization": "Bearer " + self.settings.openrouter_api_key
                    },
                    json=request,
                )
            except (httpx.HTTPError, OSError) as exc:
                with self.store.tx() as c:
                    c.execute(
                        "UPDATE reservations SET state='unknown' WHERE id=?",
                        (reservation_id,),
                    )
                    call.update(
                        state="unknown", error=type(exc).__name__, completed_at=now()
                    )
                    self.store.put(c, "call", call)
                raise FreeProviderError(
                    "The free request timed out or lost its connection; its outcome is unknown and the attempt remains counted.",
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
        choices = raw.get("choices", [])
        result_error = raw.get("error") or (
            choices and choices[0].get("finish_reason") == "error"
        )
        successful = response.is_success and not result_error
        effective_status = response.status_code
        if response.is_success and result_error:
            code = (
                raw.get("error", {}).get("code")
                if isinstance(raw.get("error"), dict)
                else None
            )
            effective_status = (
                code if isinstance(code, int) and 400 <= code < 600 else 502
            )
        usage = raw.get("usage")
        reported_cost = usage.get("cost") if isinstance(usage, dict) else None
        cost_is_valid = (
            isinstance(reported_cost, (int, float))
            and not isinstance(reported_cost, bool)
            and math.isfinite(reported_cost)
            and reported_cost >= 0
        )
        cost_is_zero = cost_is_valid and reported_cost == 0
        identity_matches = raw.get("model") == model
        artifact = self.artifacts.write(
            mission_id,
            "raw_api",
            {
                "request": request,
                "response": raw,
                "http_status": response.status_code,
                "provider": "openrouter_free",
                "catalog_entry": entry,
                "evidence_class": "measured_api",
                "sent_at": sent_at,
                "received_at": now(),
            },
        )
        if purpose.startswith("round:"):
            artifact["private_round_id"] = purpose.split(":")[1]
        # Preserve a reported nonzero charge as an anomaly, rather than hiding it
        # behind the expected zero bound. Subsequent dispatches are locked below.
        settlement = "settled" if cost_is_valid else "unknown"
        with self.store.tx() as c:
            self.store.put(c, "artifact", artifact)
            c.execute(
                "UPDATE reservations SET state=?,actual_microusd=? WHERE id=?",
                (
                    settlement,
                    micro(reported_cost) if cost_is_valid else None,
                    reservation_id,
                ),
            )
            call.update(
                state="completed" if successful else "http_error",
                actual_model=raw.get("model", "unknown"),
                artifact_id=artifact["id"],
                latency_ms=(time.perf_counter() - started) * 1000,
                http_status=response.status_code,
                result_status=effective_status,
                usage=usage,
                settlement=settlement,
                completed_at=now(),
            )
            self.store.put(c, "call", call)
            if (cost_is_valid and not cost_is_zero) or (
                successful and (not cost_is_zero or not identity_matches)
            ):
                self.store.set_setting(c, "openrouter_free_locked", True)
            if effective_status == 429:
                failure = response_error(429, raw, response.headers, model)
                until = (
                    datetime.now(UTC) + timedelta(seconds=failure.retry_after)
                ).isoformat()
                if failure.kind == "upstream_capacity":
                    cooldowns = self.store.setting(c, "openrouter_model_backoff", {})
                    cooldowns[model] = until
                    self.store.set_setting(c, "openrouter_model_backoff", cooldowns)
                elif failure.retryable:
                    self.store.set_setting(c, "openrouter_free_backoff", until)
                elif failure.kind == "daily_quota":
                    quota = self.store.setting(c, "openrouter_account_status", {})
                    if quota.get("known"):
                        quota.update(remaining=0, used=quota["limit"])
                        self.store.set_setting(c, "openrouter_account_status", quota)
            self.store.event(
                c,
                mission_id,
                "free_test.finished",
                {
                    "call_id": call_id,
                    "http_status": response.status_code,
                    "settlement": settlement,
                },
            )
        if cost_is_valid and not cost_is_zero:
            raise FreeProviderError(
                "The provider reported a nonzero charge; all further free calls are locked.",
                kind="cost_anomaly",
            )
        if not successful:
            raise response_error(effective_status, raw, response.headers, model)
        if not identity_matches or not cost_is_zero:
            raise DomainError(
                "Free response model or zero reported cost could not be verified; further calls locked",
                502,
            )
        choices = raw.get("choices", [])
        if choices and choices[0].get("finish_reason") == "length":
            raise DomainError(
                "Model reached the output token limit; response may be truncated. No automatic retry.",
                502,
            )
        content = choices[0].get("message", {}).get("content") if choices else None
        if not isinstance(content, str):
            raise DomainError("Free response has no text content", 502)
        return content, call
