"""Cheap operational checks. No provider calls, history contents or budget writes."""

import os
import sqlite3
import time
from datetime import UTC, datetime

import psutil

from .db import DomainError, now
from .postgres import WORKER_LOCK


class RuntimeHeartbeat:
    """Advisory CPU observations, not a substitute for Vercel's usage meter."""

    interval = 300

    def __init__(self, store, executor):
        self.store, self.executor = store, executor
        self.started = self.window_started = time.monotonic()
        self.last_cpu = self.accounted_cpu = 0.0
        self.next_publish = 0.0
        self.had_work = False

    def tick(self):
        self.had_work |= self.executor.busy.is_set()
        current = time.monotonic()
        if current < self.next_publish:
            return
        self.next_publish = current + self.interval
        cpu = time.process_time()
        elapsed = max(0.001, current - self.window_started)
        fraction = max(0, cpu - self.last_cpu) / elapsed
        idle_window = not self.had_work and elapsed >= self.interval - 1
        month = datetime.now(UTC).strftime('%Y-%m')
        try:
            with self.store.tx() as c:
                monthly = self.store.setting(c, 'worker_cpu_observation', {})
                known = monthly.get('known_cpu_seconds', 0) if monthly.get('month') == month else 0
                known += max(0, cpu - self.accounted_cpu)
                monthly = {'month': month, 'known_cpu_seconds': round(known, 6),
                           'billing_meter': False, 'coverage': 'instrumented worker processes only'}
                self.store.set_setting(c, 'worker_cpu_observation', monthly)
                self.store.set_setting(c, 'worker_runtime', {
                    'observed_at': now(), 'wall_seconds': round(current - self.started, 3),
                    'process_cpu_seconds': round(cpu, 6), 'window_cpu_fraction': round(fraction, 6),
                    'idle_window': idle_window, 'idle_cpu_warning': idle_window and fraction > 0.005,
                    'memory_mib': round(psutil.Process().memory_info().rss / 1024**2, 1),
                    'known_cpu_hours_this_month': round(known / 3600, 6),
                    'file_mirror_error': bool(self.executor.mirror and self.executor.mirror.last_error),
                    'commit': os.environ.get('VERCEL_GIT_COMMIT_SHA', '')[:40],
                })
        except Exception:  # noqa: BLE001 -- optional telemetry cannot stop answering
            self.next_publish = current + 60
            return  # Optional telemetry must never interrupt a model answer.
        self.accounted_cpu = self.last_cpu = cpu
        self.window_started = current
        self.had_work = False


def snapshot(store, frontend_ready):
    checks = {'frontend': 'ready' if frontend_ready else 'unavailable', 'database': 'unavailable'}
    result = {'status': 'degraded', 'checks': checks, 'checked_at': now(),
              'inference_dispatched': False, 'monitoring_version': 1}
    try:
        with store.tx() as c:
            # Read actual application metadata instead of just returning HTTP 200.
            c.execute('SELECT version FROM schema_version LIMIT 1').fetchone()
            checks['database'] = 'ready'
            if not store.remote:
                checks['worker'] = 'local_mode'
            else:
                owned = not c.execute('SELECT pg_try_advisory_xact_lock(?)', (WORKER_LOCK,)).fetchone()[0]
                runtime = store.setting(c, 'worker_runtime', {})
                if not isinstance(runtime, dict):
                    runtime = {}
                observed = runtime.get('observed_at')
                age = max(0, (datetime.now(UTC) - datetime.fromisoformat(observed)).total_seconds()) if observed else None
                checks['worker'] = 'ready' if owned and age is not None and age <= 900 else 'starting' if owned and age is None else 'unavailable'
                checks['cloud_ledger'] = 'initialized' if store.setting(c, 'cloud_ledger_ready') else 'locked'
                pending = c.execute('SELECT COUNT(*) FROM blob_files WHERE (deleted=false AND data IS NOT NULL) OR (deleted=true AND mirrored=true)').fetchone()[0]
                checks['file_mirror'] = 'deferred' if pending and runtime.get('file_mirror_error') else 'pending' if pending else 'caught_up'
                result['heartbeat_age_seconds'] = round(age) if age is not None else None
                result['worker_observation'] = {key: runtime.get(key) for key in (
                    'wall_seconds', 'process_cpu_seconds', 'window_cpu_fraction', 'idle_window',
                    'idle_cpu_warning', 'memory_mib', 'known_cpu_hours_this_month', 'commit')}
                result['warnings'] = []
                if runtime.get('idle_cpu_warning'):
                    result['warnings'].append('idle_worker_cpu_above_target')
                if runtime.get('known_cpu_hours_this_month', 0) >= 3.5:
                    result['warnings'].append('check_vercel_cpu_quota')
        if all(value in ('ready', 'local_mode', 'initialized', 'pending', 'caught_up') for value in checks.values()) and not result.get('warnings'):
            result['status'] = 'ready'
    except (sqlite3.Error, DomainError, ValueError, TypeError):
        pass  # Public diagnostics never expose credential-bearing exceptions.
    return result
