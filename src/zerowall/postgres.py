"""Postgres authority. SQLite SQL compatibility is confined to this boundary.

The transaction advisory lock preserves the existing single-writer admission
contract across API instances and the daemon, including budget reservations.
No remote failure ever falls back to an empty local database.
"""

import hashlib
import re
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal

import psycopg
from psycopg_pool import ConnectionPool

from .db import DomainError, Store

TRANSACTION_LOCK = 5714319001
WORKER_LOCK = 5714319002


class StorageUnavailable(DomainError, sqlite3.OperationalError):
    def __init__(self):
        DomainError.__init__(
            self,
            "Shared storage is unavailable; saved work remains in the remote authority. No local fallback was used.",
            503,
        )


class Row:
    def __init__(self, names, values):
        self.names = names
        # SUM(bigint) is NUMERIC on Postgres. The ledger remains exact integer
        # microdollars, as with SQLite, before public projections divide by 1e6.
        self.values = tuple(
            int(value)
            if isinstance(value, Decimal) and value == value.to_integral_value()
            else value
            for value in values
        )

    def __getitem__(self, key):
        return (
            self.values[self.names.index(key)]
            if isinstance(key, str)
            else self.values[key]
        )

    def __iter__(self):
        return iter(self.values)

    def keys(self):
        return self.names


def row_factory(cursor):
    names = (
        tuple(column.name for column in cursor.description)
        if cursor.description
        else ()
    )
    return lambda values: Row(names, values)


def translate(sql, parameters):
    # Only repository SQL is translated; all user values remain bound parameters.
    sql = re.sub(
        r"json_extract\(body,\s*'\$\.([a-zA-Z0-9_.]+)'\)",
        lambda m: "(body::jsonb #>> '{" + m[1].replace(".", ",") + "}')",
        sql,
    )
    sql = re.sub(r"\browid\b", "ordinal", sql)
    if parameters is None:
        return sql
    # Respect SQL string literals, including doubled quotes. Psycopg still needs
    # literal percent signs escaped when a parameter sequence is supplied.
    pieces = re.split(r"('(?:''|[^'])*')", sql)
    return "".join(
        part.replace("%", "%%")
        if index % 2
        else part.replace("%", "%%").replace("?", "%s")
        for index, part in enumerate(pieces)
    )


class Connection:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, parameters=None):
        result = self.raw.execute(translate(sql, parameters), parameters)
        if re.match(
            r"\s*(?:INSERT INTO|UPDATE|DELETE FROM)\s+jobs\b", sql, re.IGNORECASE
        ):
            self.raw.execute("SELECT pg_notify('zerowall_jobs','')")
        return result


DDL = """
CREATE SCHEMA IF NOT EXISTS zerowall;
REVOKE ALL ON SCHEMA zerowall FROM PUBLIC;
SET LOCAL search_path=zerowall,pg_catalog;
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
INSERT INTO schema_version VALUES(1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,kind TEXT NOT NULL,mission_id TEXT NOT NULL,body TEXT NOT NULL,ordinal BIGSERIAL UNIQUE);
CREATE INDEX IF NOT EXISTS records_lookup ON records(kind,mission_id);
CREATE TABLE IF NOT EXISTS events(seq BIGSERIAL PRIMARY KEY,mission_id TEXT NOT NULL,type TEXT NOT NULL,body TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reservations(id TEXT PRIMARY KEY,mission_id TEXT NOT NULL,call_id TEXT UNIQUE NOT NULL,maximum_microusd BIGINT NOT NULL,actual_microusd BIGINT,state TEXT NOT NULL,body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,mission_id TEXT NOT NULL,kind TEXT NOT NULL,target_id TEXT NOT NULL,state TEXT NOT NULL,body TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(state,created_at);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS idempotency(key TEXT PRIMARY KEY,request_hash TEXT NOT NULL,response TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_fts(chat_id TEXT,version_id TEXT,chunk_id TEXT,title TEXT,text TEXT);
CREATE INDEX IF NOT EXISTS source_search ON source_fts USING GIN(to_tsvector('simple',coalesce(title,'') || ' ' || coalesce(text,'')));
CREATE TABLE IF NOT EXISTS blob_files(path TEXT PRIMARY KEY,sha256 TEXT NOT NULL,size BIGINT NOT NULL,data BYTEA,mirrored BOOLEAN NOT NULL DEFAULT false,deleted BOOLEAN NOT NULL DEFAULT false);
"""


class PostgresStore(Store):
    remote = True

    def __init__(self, dsn):
        self.dsn = dsn
        self.path = "postgres:" + hashlib.sha256(dsn.encode()).hexdigest()[:24]
        self.current = ContextVar("zerowall_transaction_" + self.path, default=None)
        self.pool = ConnectionPool(
            dsn,
            min_size=0,
            max_size=4,
            timeout=15,
            kwargs={
                "autocommit": True,
                "prepare_threshold": None,
                "row_factory": row_factory,
                "connect_timeout": 10,
            },
            open=True,
        )
        try:
            with self.pool.connection() as raw, raw.transaction():
                raw.execute("SELECT pg_advisory_xact_lock(%s)", (TRANSACTION_LOCK,))
                raw.execute(DDL, prepare=False)
        except psycopg.Error:
            self.pool.close()
            raise StorageUnavailable() from None

    @contextmanager
    def tx(self):
        existing = self.current.get()
        try:
            if existing is not None:
                with existing.transaction():
                    yield Connection(existing)
                return
            with self.pool.connection() as raw, raw.transaction():
                raw.execute("SET LOCAL search_path=zerowall,pg_catalog")
                raw.execute("SELECT pg_advisory_xact_lock(%s)", (TRANSACTION_LOCK,))
                token = self.current.set(raw)
                try:
                    yield Connection(raw)
                finally:
                    self.current.reset(token)
        except psycopg.IntegrityError:
            raise sqlite3.IntegrityError("Shared storage constraint failed") from None
        except (psycopg.Error, TimeoutError):
            raise StorageUnavailable() from None

    def close(self):
        self.pool.close()

    @contextmanager
    def operation_lock(self, key):
        lock = int.from_bytes(
            hashlib.sha256(key.encode()).digest()[:8], "big", signed=True
        )
        try:
            with psycopg.connect(
                self.dsn, autocommit=True, prepare_threshold=None, connect_timeout=10
            ) as connection:
                connection.execute("SELECT pg_advisory_lock(%s)", (lock,))
                try:
                    yield
                finally:
                    connection.execute("SELECT pg_advisory_unlock(%s)", (lock,))
        except psycopg.Error:
            raise StorageUnavailable() from None


class WorkerLock:
    """A dedicated session, never a transaction-pool connection or expiring TTL.

    Lost ownership prevents dispatch but does not forbid saving an answer already
    received. The lock connection is never silently reconnected.
    """

    def __init__(self, store):
        self.store, self.connection = store, None

    def acquire(self):
        connection = None
        try:
            connection = psycopg.connect(
                self.store.dsn,
                autocommit=True,
                prepare_threshold=None,
                connect_timeout=10,
            )
            if not connection.execute(
                "SELECT pg_try_advisory_lock(%s)", (WORKER_LOCK,)
            ).fetchone()[0]:
                connection.close()
                raise DomainError("Another council worker owns the shared queue", 503)
            self.connection = connection
            self.connection.execute("LISTEN zerowall_jobs")
            self.connection.execute("LISTEN zerowall_files")
        except psycopg.Error:
            if connection is not None:
                connection.close()
            self.connection = None
            raise StorageUnavailable() from None

    def healthy(self):
        try:
            return (
                self.connection is not None
                and not self.connection.closed
                and self.connection.execute("SELECT 1").fetchone()[0] == 1
            )
        except psycopg.Error:
            return False

    @property
    def disconnected(self):
        return self.connection is None or bool(self.connection.closed)

    def wake(self):
        # A separate pooled session wakes LISTEN without cancelling an answer.
        with self.store.tx() as c:
            c.execute("SELECT pg_notify('zerowall_jobs','')")

    def release(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def wait(self, timeout=60):
        try:
            for notification in self.connection.notifies(timeout=timeout, stop_after=1):
                return notification.channel
        except psycopg.Error:
            raise StorageUnavailable() from None
