import math
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from .db import DomainError


class FreeProviderError(DomainError):
    def __init__(
        self, message, *, kind, retryable=False, retry_after=0, model=None, code=503
    ):
        super().__init__(message, code)
        self.kind, self.retryable = kind, retryable
        self.retry_after, self.model = retry_after, model


def retry_delay(headers, default=20):
    value = headers.get("Retry-After")
    try:
        seconds = float(value)
        if math.isfinite(seconds) and seconds >= 0:
            return min(31536000, max(1, seconds))
    except (ValueError, TypeError):
        try:
            return min(
                31536000,
                max(
                    1,
                    (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds(),
                ),
            )
        except (ValueError, TypeError, OverflowError):
            pass
    try:
        reset = float(headers.get("X-RateLimit-Reset", ""))
        if math.isfinite(reset):
            if reset > 1e11:
                reset /= 1000
            return min(31536000, max(1, reset - datetime.now(UTC).timestamp()))
    except (ValueError, TypeError):
        pass
    return default


def response_error(status, raw, headers, model):
    error = raw.get("error", {})
    error = error if isinstance(error, dict) else {}
    metadata = error.get("metadata", {})
    metadata = metadata if isinstance(metadata, dict) else {}
    text = str(error.get("message", "")).lower()
    source = str(metadata.get("limit_source", ""))
    if status == 429:
        if "per-day" in text or "daily" in text or "per_day" in source:
            return FreeProviderError(
                "OpenRouter's daily free-request quota is exhausted. Saved answers are intact; wait for the quota reset.",
                kind="daily_quota",
                model=model,
                code=429,
            )
        shared = source == "upstream_provider_shared_pool"
        return FreeProviderError(
            f"{model} is temporarily unavailable in its shared free provider pool. Your API key is not the cause."
            if shared
            else "OpenRouter is temporarily rate limiting free requests.",
            kind="upstream_capacity" if shared else "platform_rate_limit",
            retryable=True,
            retry_after=retry_delay(headers),
            model=model,
            code=429,
        )
    if status in (408, 500, 502, 503, 504):
        return FreeProviderError(
            f"The free provider returned HTTP {status}; this turn can be retried after a wait.",
            kind="provider_temporary",
            retryable=True,
            retry_after=retry_delay(headers),
            model=model,
        )
    messages = {
        401: (
            "credential",
            "The saved OpenRouter API key was rejected. Update the key before continuing.",
        ),
        402: (
            "account",
            "OpenRouter rejected the account or credit state. Paid routing remains disabled.",
        ),
        403: (
            "access",
            "OpenRouter refused access to this free model. Check account/model access settings.",
        ),
        404: ("model_unavailable", "The selected free model is no longer available."),
    }
    kind, message = messages.get(
        status,
        ("request_rejected", f"OpenRouter rejected this request (HTTP {status})."),
    )
    return FreeProviderError(message, kind=kind, model=model, code=502)
