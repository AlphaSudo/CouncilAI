"""Vercel Daemon entrypoint. No inbound server and no worker in API instances."""

import signal
import threading
import time

from .api import create_app
from .db import DomainError
from .hosting import validate_runtime
from .settings import Settings
from .cloud_operations import RuntimeHeartbeat


def main():
    settings = Settings()
    if settings.storage_backend != "supabase" or settings.role != "worker":
        raise ValueError(
            "The cloud worker requires Supabase storage and ZEROWALL_ROLE=worker"
        )
    shutdown = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: shutdown.set())
    signal.signal(signal.SIGINT, lambda *_: shutdown.set())
    app = create_app(settings, run_worker=False)
    executor, research = app.state.executor, app.state.research
    validate_runtime(settings, research.store, worker=True)
    try:
        while not shutdown.is_set():
            try:
                executor.start()
                break
            except DomainError as error:
                if error.code != 503:
                    raise
                shutdown.wait(5)  # An earlier deployment may still be finishing.
        if not executor.thread:
            return
        heartbeat = RuntimeHeartbeat(research.store, executor)
        next_idle_check = 0
        while executor.thread.is_alive() and not shutdown.wait(1):
            # Active requests retain their frequent ownership checks. Idle
            # supervision uses local state and one check per minute.
            check_due = executor.busy.is_set() or time.monotonic() >= next_idle_check
            if executor.ownership.disconnected or (check_due and executor.ownership_lost()):
                executor.stop.set()
            if check_due:
                next_idle_check = time.monotonic() + 60
            heartbeat.tick()
        # Drain the in-flight cycle before releasing ownership. Vercel's daemon
        # termination grace period is configured to 3600 seconds for this reason.
        executor.drain()
        while executor.thread.is_alive():
            executor.thread.join(timeout=1)
    finally:
        executor.close()
        research.store.close()
        research.artifacts.files.objects.close()


if __name__ == "__main__":
    main()
