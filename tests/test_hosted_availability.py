import importlib.util
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from zerowall import cloud_operations as operations
from zerowall.durable_files import FileMirror

spec = importlib.util.spec_from_file_location('availability_script', Path(__file__).parents[1] / 'scripts/check_hosted_availability.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def test_public_health_is_cached_and_never_exposes_private_settings(client, app, monkeypatch, tmp_path):
    app.state.research.settings.frontend = tmp_path
    (tmp_path / 'index.html').write_text('test page')
    store = app.state.research.store
    with store.tx() as c:
        store.set_setting(c, 'private-example', {'secret': 'private-data-must-not-be-public'})
    calls = []
    original = operations.snapshot
    monkeypatch.setattr(operations, 'snapshot', lambda *args: calls.append(1) or original(*args))
    first = client.get('/api/operations/status')
    second = client.get('/api/operations/status')
    assert first.status_code == second.status_code == 200
    assert first.json()['checks']['database'] == 'ready'
    assert first.json()['inference_dispatched'] is False
    assert first.headers['cache-control'] == 'no-store'
    assert len(calls) == 1
    assert 'private-data-must-not-be-public' not in first.text
    with store.tx() as c:
        assert c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0] == 0


def test_failed_storage_health_hides_connection_errors():
    class BrokenStore:
        def tx(self):
            raise sqlite3.OperationalError('private database password')
    result = operations.snapshot(BrokenStore(), True)
    assert result['status'] == 'degraded'
    assert result['checks']['database'] == 'unavailable'
    assert 'password' not in json.dumps(result)


def test_runtime_observation_keeps_financial_authority_and_detects_idle_cpu(app, monkeypatch):
    clock, cpu = [0.0], [0.2]
    monkeypatch.setattr(operations.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(operations.time, 'process_time', lambda: cpu[0])
    store = app.state.research.store
    authority = {'authorized_cap_usd': 24, 'additional_payment_authority_usd': 0}
    with store.tx() as c:
        store.set_setting(c, 'token_factory_spending_authority', authority)
        store.set_setting(c, 'live_verification', {'unchanged': True})
    busy = threading.Event()
    observer = operations.RuntimeHeartbeat(store, SimpleNamespace(busy=busy, mirror=None))
    observer.tick()
    busy.set()
    clock[0] = 150
    observer.tick()
    busy.clear()
    clock[0], cpu[0] = 300, 0.3
    observer.tick()
    with store.tx() as c:
        assert not store.setting(c, 'worker_runtime')['idle_window']
    clock[0], cpu[0] = 600, 3.3
    observer.tick()
    with store.tx() as c:
        runtime = store.setting(c, 'worker_runtime')
        assert runtime['idle_window'] and runtime['idle_cpu_warning']
        assert store.setting(c, 'token_factory_spending_authority') == authority
        assert store.setting(c, 'live_verification') == {'unchanged': True}
        assert store.setting(c, 'worker_cpu_observation')['known_cpu_seconds'] == 3.3
        assert c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0] == 0


def test_mirror_wakes_promptly_and_shutdown_does_not_wait_for_backoff():
    first, second = threading.Event(), threading.Event()
    calls = []
    def flush():
        calls.append(1)
        (first if len(calls) == 1 else second).set()
        return 0
    mirror = FileMirror(SimpleNamespace(flush=flush))
    mirror.start()
    try:
        assert first.wait(1)
        mirror.wake()
        assert second.wait(1)
    finally:
        mirror.close()
    assert not mirror.thread.is_alive()


def test_scheduled_checks_end_after_judging_instead_of_running_forever():
    assert checker.scheduled_window_open(datetime(2026, 12, 15, 19, 59, tzinfo=UTC))
    assert not checker.scheduled_window_open(datetime(2026, 12, 15, 20, 1, tzinfo=UTC))
    assert not checker.scheduled_window_open(datetime(2027, 12, 1, tzinfo=UTC))


def test_checker_only_uses_anonymous_gets_and_waits_for_cold_start():
    calls, waits = [], []
    body = {'monitoring_version': 1, 'status': 'ready', 'inference_dispatched': False,
            'checks': {'frontend': 'ready', 'database': 'ready', 'worker': 'ready',
                       'cloud_ledger': 'initialized', 'file_mirror': 'caught_up'}}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, count): return json.dumps(body).encode()
    def open_request(request, timeout):
        calls.append(request)
        assert request.get_method() == 'GET'
        assert not request.has_header('Authorization') and request.data is None
        if len(calls) == 1:
            raise HTTPError(request.full_url, 503, 'starting', {}, None)
        return Response()
    good, report = checker.check('https://council.example', pause=waits.append,
                                 opener=SimpleNamespace(open=open_request))
    assert good and report['checks']['worker'] == 'ready'
    assert len(calls) == 2 and waits == [20]
    assert calls[-1].full_url == 'https://council.example/api/operations/status'


@pytest.mark.parametrize('url', ['http://council.example', 'https://user:password@council.example', 'https://council.example/?key=secret'])
def test_checker_refuses_credentials_or_unencrypted_origins(url):
    with pytest.raises(ValueError):
        checker.check(url)
