"""Explicit offline cutover. No cloud initialization can create fresh credit.

The default command inventories only. Apply requires the local executor stopped,
an empty destination, and an explicit choice about private history. A migration
marker is the last item committed. Local authorization is disabled BEFORE the
remote copy; failure leaves the source data intact but inference locked.
"""

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .db import DomainError, Store, digest, now
from .durable_files import DurableFiles
from .postgres import PostgresStore
from .process_lock import ProcessLock
from .settings import Settings

TABLES = ("records", "events", "reservations", "jobs", "settings", "idempotency")


def snapshot(directory):
    directory = Path(directory).resolve()
    database = directory / "zerowall.sqlite3"
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as c:
        c.row_factory = sqlite3.Row
        c.execute("BEGIN")
        data = {
            table: [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM "
                    + table
                    + (" ORDER BY rowid" if table != "events" else " ORDER BY seq")
                )
            ]
            for table in TABLES
        }
        data["source_fts"] = (
            [dict(r) for r in c.execute("SELECT * FROM source_fts")]
            if c.execute(
                "SELECT 1 FROM sqlite_master WHERE name='source_fts'"
            ).fetchone()
            else []
        )
    blobs = {}
    for prefix in ("artifacts", "source-blobs", "exports", "review-exports"):
        for path in (directory / prefix).rglob("*"):
            if path.is_file() and path.suffix != ".tmp":
                if not path.resolve().is_relative_to(directory):
                    raise DomainError("Migration file escapes the data directory", 422)
                content = path.read_bytes()
                blobs[path.relative_to(directory).as_posix()] = content
    return data, blobs


def inventory(data, blobs):
    committed = sum(
        r["actual_microusd"] if r["state"] == "settled" else r["maximum_microusd"]
        for r in data["reservations"]
    )
    return {
        "schema_version": 1,
        "tables": {table: len(rows) for table, rows in data.items()},
        "snapshot_sha256": digest(data),
        "files": len(blobs),
        "file_bytes": sum(map(len, blobs.values())),
        "files_manifest_sha256": digest(
            {
                key: hashlib.sha256(value).hexdigest()
                for key, value in sorted(blobs.items())
            }
        ),
        "committed_microusd_all_providers": committed,
        "paid_inference_dispatched": False,
    }


def cutover(directory, destination, *, include_history=False):
    directory = Path(directory).resolve()
    lock = ProcessLock(directory / "executor.lock")
    lock.acquire()
    try:
        data, blobs = snapshot(directory)
        if any(row["state"] in ("queued", "running") for row in data["jobs"]) or any(
            row["state"] == "reserved" for row in data["reservations"]
        ):
            raise DomainError(
                "Finish, pause or stop queued/running local work before cutover; recover unknown calls explicitly first",
                409,
            )
        # Refuse an occupied destination before disabling local inference.
        with destination.tx() as c:
            if any(
                c.execute("SELECT 1 FROM " + table + " LIMIT 1").fetchone()
                for table in (*TABLES, "blob_files", "source_fts")
            ):
                raise DomainError(
                    "Migration requires an empty destination; existing cloud data was left untouched",
                    409,
                )
        local = Store(directory / "zerowall.sqlite3")
        with local.tx() as c:
            local.set_setting(c, "live_verification", {})
            authority = local.setting(c, "token_factory_spending_authority", {})
            authority["user_testing_authorized"] = False
            local.set_setting(c, "token_factory_spending_authority", authority)
            local.set_setting(
                c, "cloud_cutover", {"at": now(), "local_inference_disabled": True}
            )
        report = inventory(data, blobs)
        # Both destinations require explicit reauthorization after the cutover.
        selected = (
            data
            if include_history
            else {
                "records": [],
                "events": [],
                "reservations": data["reservations"],
                "jobs": [],
                "settings": data["settings"],
                "idempotency": [],
                "source_fts": [],
            }
        )
        files = DurableFiles(directory / ".cloud-cache", destination)
        with destination.tx() as c:
            # Recheck under the same transaction as the entire import.
            if any(
                c.execute("SELECT 1 FROM " + table + " LIMIT 1").fetchone()
                for table in (*TABLES, "blob_files", "source_fts")
            ):
                raise DomainError(
                    "Destination changed during cutover; no import was committed", 409
                )
            for table, rows in selected.items():
                for row in rows:
                    names = list(row)
                    c.execute(
                        "INSERT INTO "
                        + table
                        + "("
                        + ",".join(names)
                        + ") VALUES("
                        + ",".join("?" for _ in names)
                        + ")",
                        tuple(row[name] for name in names),
                    )
            if include_history:
                for key, content in blobs.items():
                    files.write(key, content)
            c.execute(
                "SELECT setval(pg_get_serial_sequence('events','seq'),COALESCE((SELECT MAX(seq) FROM events),1),(SELECT COUNT(*)>0 FROM events))"
            )
            destination.set_setting(c, "live_verification", {})
            authority = destination.setting(c, "token_factory_spending_authority", {})
            authority["user_testing_authorized"] = False
            destination.set_setting(c, "token_factory_spending_authority", authority)
            destination.set_setting(
                c,
                "cloud_ledger_ready",
                {
                    "imported_at": now(),
                    "includes_private_history": include_history,
                    **report,
                },
            )
        return report
    finally:
        lock.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--include-history",
        action="store_true",
        help="Explicitly copy private conversations and source documents; default copies the ledger only",
    )
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps(inventory(*snapshot(args.source)), indent=2))
        return
    settings = Settings()
    if not settings.database_url:
        raise ValueError("Apply requires the explicit Supabase configuration")
    destination = PostgresStore(settings.database_url)
    try:
        print(
            json.dumps(
                cutover(args.source, destination, include_history=args.include_history),
                indent=2,
            )
        )
    finally:
        destination.close()


if __name__ == "__main__":
    main()
