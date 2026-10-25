"""Real Postgres integration; optional only when no dedicated test DB is supplied.

Run against an EMPTY, DISPOSABLE database using ZEROWALL_TEST_DATABASE_URL.
No production .env credential is read for the test authority.
"""

import hashlib
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx
import pytest

from zerowall.db import DomainError
from zerowall.durable_files import DurableFiles, SupabaseObjects
from zerowall.postgres import PostgresStore, WorkerLock, translate


def test_translation_keeps_values_and_literal_question_marks():
    assert (
        translate("SELECT '?' AS q, ? AS value, '20%' AS pct", ("bound?",))
        == "SELECT '?' AS q, %s AS value, '20%%' AS pct"
    )


@pytest.mark.parametrize('key,bearer', [('sb_secret_' + 'offline-fixture', False), ('legacy-jwt-fixture', True)])
def test_storage_authenticates_new_server_keys_without_treating_them_as_jwts(key, bearer):
    def handler(request):
        assert request.headers['apikey'] == key
        assert ('authorization' in request.headers) is bearer
        if bearer:
            assert request.headers['authorization'] == 'Bearer ' + key
        return httpx.Response(200, content=b'complete source')

    objects = SupabaseObjects('https://example.supabase.co', key, 'private', httpx.MockTransport(handler))
    try:
        assert objects.get('source') == b'complete source'
        objects.put('source', b'complete source')
        objects.delete('source')
    finally:
        objects.close()


def test_shared_ordering_json_rows_rollback_and_serialized_admission(pg):
    other = PostgresStore(pg.dsn)
    try:
        with pg.tx() as c:
            pg.put(c, "sample", {"id": "first", "mission_id": "mission", "amount": 3})
            pg.put(c, "sample", {"id": "second", "mission_id": "mission"})
            pg.put(c, "sample", {"id": "first", "mission_id": "mission", "amount": 4})
            assert (
                c.execute(
                    "SELECT json_extract(body,'$.amount') FROM records WHERE id=?",
                    ("first",),
                ).fetchone()[0]
                == "4"
            )
        with other.tx() as c:
            assert [x["id"] for x in other.list(c, "sample", "mission")] == [
                "first",
                "second",
            ]
            assert dict(
                c.execute(
                    "SELECT id,kind FROM records WHERE id=?", ("first",)
                ).fetchone()
            ) == {"id": "first", "kind": "sample"}
        with pytest.raises(ValueError), pg.tx() as c:
            pg.put(c, "sample", {"id": "rollback"})
            raise ValueError("rollback")

        def admission(store):
            with store.tx() as c:
                used = c.execute(
                    "SELECT COALESCE(SUM(maximum_microusd),0) FROM reservations"
                ).fetchone()[0]
                if used + 15000000 > 24000000:
                    return False
                c.execute(
                    "INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",
                    (
                        str(id(store)),
                        "mission",
                        str(id(store)),
                        15000000,
                        None,
                        "unknown",
                        "{}",
                    ),
                )
                return True

        with ThreadPoolExecutor(2) as executor:
            assert sorted(executor.map(admission, (pg, other))) == [False, True]
        with pg.tx() as c:
            assert not c.execute("SELECT 1 FROM records WHERE id='rollback'").fetchone()
            assert (
                c.execute("SELECT SUM(maximum_microusd) FROM reservations").fetchone()[
                    0
                ]
                == 15000000
            )
    finally:
        other.close()


def test_outbox_survives_cache_destruction_and_storage_outage(pg, tmp_path):
    objects, requests = {}, []
    unavailable = [True]

    def handler(request):
        requests.append(request.method)
        assert request.headers["apikey"] == "test-private-key"
        if unavailable[0]:
            return httpx.Response(503)
        key = request.url.path.split("/private/", 1)[-1]
        if request.method == "POST":
            if key in objects:
                return httpx.Response(409)
            objects[key] = request.content
            return httpx.Response(200)
        if request.method == "GET":
            return httpx.Response(200, content=objects[key])
        for key in json.loads(request.content)["prefixes"]:
            objects.pop(key, None)
        return httpx.Response(200)

    api = SupabaseObjects(
        "https://example.supabase.co",
        "test-private-key",
        "private",
        httpx.MockTransport(handler),
    )
    files = DurableFiles(tmp_path, pg, api)
    data = b"A complete original public response, never truncated."
    sha = files.write("artifacts/mission/answer.json", data)
    with pytest.raises(DomainError):
        files.flush()
    shutil.rmtree(tmp_path)
    assert files.read("artifacts/mission/answer.json", sha) == data
    unavailable[0] = False
    assert files.flush() == 1
    shutil.rmtree(tmp_path)
    assert files.read("artifacts/mission/answer.json", sha) == data
    assert requests.count("POST") == 2
    with pg.tx() as c:
        assert c.execute("SELECT data FROM blob_files").fetchone()[0] is None
    objects["artifacts/mission/answer.json"] = b"corrupt"
    shutil.rmtree(tmp_path)
    with pytest.raises(DomainError, match="integrity"):
        files.read("artifacts/mission/answer.json", sha)
    files.delete("artifacts/mission/answer.json")
    files.flush()
    assert not objects
    api.close()


def test_nested_file_write_rolls_back_with_manifest(pg, tmp_path):
    files = DurableFiles(tmp_path, pg)
    with pytest.raises(RuntimeError), pg.tx() as c:
        files.write("source-blobs/rollback", b"document")
        pg.put(c, "sample", {"id": "manifest"})
        raise RuntimeError("manifest transaction aborted")
    with pg.tx() as c:
        assert not c.execute("SELECT 1 FROM blob_files").fetchone()
        assert not c.execute("SELECT 1 FROM records").fetchone()
    with pytest.raises(DomainError):
        files.read("source-blobs/rollback", hashlib.sha256(b"document").hexdigest())


def test_worker_ownership_and_unknown_recovery_do_not_replay(pg):
    first, second = WorkerLock(pg), WorkerLock(pg)
    first.acquire()
    assert first.healthy()
    with pytest.raises(DomainError, match="Another council worker"):
        second.acquire()
    with pg.tx() as c:
        c.execute(
            "INSERT INTO reservations VALUES(?,?,?,?,?,?,?)",
            ("reserve", "mission", "call", 120000, None, "reserved", "{}"),
        )
    first.release()
    second.acquire()
    try:
        pg.recover()
        with pg.tx() as c:
            row = c.execute(
                "SELECT state,maximum_microusd FROM reservations"
            ).fetchone()
            assert tuple(row) == ("unknown", 120000)
            assert c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    finally:
        second.release()


def test_queue_and_file_notifications_wake_a_long_idle_wait(pg, tmp_path):
    owner = WorkerLock(pg)
    owner.acquire()
    try:
        with ThreadPoolExecutor(1) as executor:
            waiting = executor.submit(owner.wait, 60)
            owner.wake()
            assert waiting.result(timeout=3) == 'zerowall_jobs'
            waiting = executor.submit(owner.wait, 60)
            DurableFiles(tmp_path, pg).write('source-blobs/notify', b'complete document')
            assert waiting.result(timeout=3) == 'zerowall_files'
    finally:
        owner.release()


def test_operational_health_checks_the_worker_without_changing_the_ledger(pg):
    from zerowall.cloud_operations import snapshot
    owner = WorkerLock(pg)
    owner.acquire()
    try:
        with pg.tx() as c:
            pg.set_setting(c, 'cloud_ledger_ready', {'mode': 'test'})
            pg.set_setting(c, 'worker_runtime', {'observed_at': datetime.now(UTC).isoformat()})
            pg.set_setting(c, 'private', {'secret': 'not-public'})
        status = snapshot(pg, True)
        assert status['status'] == 'ready'
        assert status['checks']['worker'] == 'ready'
        assert 'not-public' not in json.dumps(status)
        with pg.tx() as c:
            assert c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0] == 0
        owner.release()
        assert snapshot(pg, True)['checks']['worker'] == 'unavailable'
    finally:
        owner.release()
