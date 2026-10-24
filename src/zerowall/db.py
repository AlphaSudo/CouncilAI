"""SQLite transaction boundary shared by state, audit, queue and financial ledger."""

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime


def now():
    return datetime.now(UTC).isoformat()


def uid(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class DomainError(Exception):
    def __init__(self, message, code=409):
        self.message, self.code = message, code


class Store:
    remote = False
    def __init__(self, path):
        self.path = str(path)
        with self.tx() as c:
            c.executescript("""
              CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
              INSERT OR IGNORE INTO schema_version VALUES(1);
              CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, kind TEXT NOT NULL, mission_id TEXT NOT NULL, body TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS records_lookup ON records(kind, mission_id);
              CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, mission_id TEXT NOT NULL, type TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS reservations(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, call_id TEXT UNIQUE NOT NULL, maximum_microusd INTEGER NOT NULL, actual_microusd INTEGER, state TEXT NOT NULL, body TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, kind TEXT NOT NULL, target_id TEXT NOT NULL, state TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, body TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS idempotency(key TEXT PRIMARY KEY, request_hash TEXT NOT NULL, response TEXT NOT NULL);
            """)

    @contextmanager
    def tx(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=15000")
        try:
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def get(self, c, record_id, kind=None):
        row = c.execute(
            "SELECT kind,body FROM records WHERE id=?", (record_id,)
        ).fetchone()
        if not row or (kind and row["kind"] != kind):
            raise DomainError("Record not found", 404)
        return json.loads(row["body"])

    def list(self, c, kind, mission_id):
        return [
            json.loads(r[0])
            for r in c.execute(
                "SELECT body FROM records WHERE kind=? AND mission_id=? ORDER BY rowid",
                (kind, mission_id),
            )
        ]

    def put(self, c, kind, body):
        body.setdefault("schema_version", 1)
        body.setdefault("created_at", now())
        c.execute(
            "INSERT INTO records(id,kind,mission_id,body) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
            (body["id"], kind, body.get("mission_id", body["id"]), canonical(body)),
        )
        return body

    def event(self, c, mission_id, event_type, body):
        # Content is explicitly chosen by each transition: never publish private submissions.
        c.execute(
            "INSERT INTO events(mission_id,type,body,created_at) VALUES(?,?,?,?)",
            (mission_id, event_type, canonical(body), now()),
        )

    def setting(self, c, key, default=None):
        row = c.execute("SELECT body FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, c, key, value):
        c.execute(
            "INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET body=excluded.body",
            (key, canonical(value)),
        )

    def check(self, record, expected):
        if record["revision"] != expected:
            raise DomainError("Revision changed. Refresh before acting.")

    def healthy(self):
        with self.tx() as c:
            return c.execute("SELECT 1").fetchone()[0] == 1

    def close(self):
        pass

    @contextmanager
    def operation_lock(self, key):
        yield

    def recover(self):
        with self.tx() as c:
            # A process may have died after sending but before settling. Never automatically replay it.
            c.execute("UPDATE reservations SET state='unknown' WHERE state='reserved'")
            c.execute(
                "UPDATE reservations SET maximum_microusd=0,actual_microusd=0,state='released' WHERE state='held'"
            )
            for row in c.execute(
                "SELECT body FROM records WHERE kind='call'"
            ).fetchall():
                call = json.loads(row[0])
                if call["state"] == "dispatching":
                    call.update(
                        state="unknown",
                        error="Process restarted before settlement",
                        completed_at=now(),
                    )
                    self.put(c, "call", call)
            for row in c.execute(
                "SELECT body FROM records WHERE kind='run'"
            ).fetchall():
                run = json.loads(row[0])
                if run["state"] == "running":
                    run.update(state="interrupted", completed_at=now())
                    self.put(c, "run", run)
            for row in c.execute("SELECT * FROM jobs WHERE state='running'").fetchall():
                c.execute(
                    "UPDATE jobs SET state='interrupted' WHERE id=?", (row["id"],)
                )
                self.event(
                    c,
                    row["mission_id"],
                    "job.interrupted",
                    {
                        "job_id": row["id"],
                        "reason": "Executor restarted; inspect attempts before creating new work.",
                    },
                )
                if row["kind"] == "chat":
                    record = self.get(c, row["target_id"], "chat")
                    if (record.get("active_turn") or {}).get("job_id") in (None, row["id"]):
                        record["active_turn"] = None
                    if record["status"] == "running":
                        record.update(status="interrupted", active_turn=None)
                    self.put(c, "chat", record)
                elif row["kind"] in ("round", "review"):
                    record = self.get(c, row["target_id"], "round")
                    record["status"] = "interrupted"
                    self.put(c, "round", record)
                else:
                    record = self.get(c, row["target_id"], "experiment")
                    record["status"] = "interrupted"
                    self.put(c, "experiment", record)


def open_store(settings):
    if getattr(settings, "database_url", ""):
        from .postgres import PostgresStore
        return PostgresStore(settings.database_url)
    return Store(settings.data / "zerowall.sqlite3")
