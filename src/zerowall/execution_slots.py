"""Conservative per-provider admission; opening parallelism stays disabled."""

import functools
import threading

from .db import DomainError

_guard = threading.Lock()
_providers = {}


def one_model_per_provider(function):
    @functools.wraps(function)
    def call(self, mission_id, prompt, max_output=4096, model=None, **kwargs):
        entry = {**self.entries(), **self.fallback_entries()}.get(model, {})
        with _guard:
            slot = _providers.setdefault(
                entry.get("provider", "unknown"), threading.BoundedSemaphore(1)
            )
        if not slot.acquire(timeout=5):
            raise DomainError(
                "A model call for this provider is already in flight; saved work remains available",
                429,
            )
        try:
            return function(self, mission_id, prompt, max_output, model=model, **kwargs)
        finally:
            slot.release()

    return call


def opening_parallelism_allowed(descriptor):
    if descriptor.get("parallel_openings"):
        raise DomainError(
            "Parallel openings remain disabled until durable reveal-barrier and quota pilot evidence is approved",
            412,
        )
    return False
