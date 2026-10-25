"""Hash-checked disposable cache and a transactional, durable blob outbox.

Cloud writes first enter Postgres, in the same transaction as their manifest
when called inside Store.tx(). Storage mirroring happens outside that transaction;
a Storage API outage cannot erase a received answer or block its publication.
"""

import hashlib
import os
import threading
import uuid
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import httpx

from .db import DomainError


class SupabaseObjects:
    def __init__(self, url, key, bucket, transport=None):
        self.base = url.rstrip("/") + "/storage/v1"
        self.bucket = quote(bucket, safe="")
        headers = {'apikey': key}
        # New server keys are opaque API keys, not JWTs. Only legacy service_role
        # JWTs belong on Authorization; the gateway authenticates sb_secret via apikey.
        if not key.startswith('sb_secret_'):
            headers['Authorization'] = 'Bearer ' + key
        self.client = httpx.Client(
            headers=headers,
            timeout=30,
            transport=transport,
            follow_redirects=False,
        )

    def address(self, path):
        return "/object/" + self.bucket + "/" + quote(path, safe="/")

    def get(self, path):
        response = self.client.get(
            self.base
            + self.address(path).replace("/object/", "/object/authenticated/", 1)
        )
        if response.status_code != 200:
            raise DomainError(
                "Private file storage is unavailable; the saved manifest was retained",
                503,
            )
        return response.content

    def put(self, path, data):
        response = self.client.post(
            self.base + self.address(path),
            content=data,
            headers={"Content-Type": "application/octet-stream", "x-upsert": "false"},
        )
        if response.status_code in (400, 409) and self.get(path) == data:
            return  # An interrupted upload may already have succeeded.
        if response.status_code not in (200, 201):
            raise DomainError(
                "Private file upload deferred; durable database bytes were retained",
                503,
            )

    def delete(self, path):
        response = self.client.request(
            "DELETE", self.base + "/object/" + self.bucket, json={"prefixes": [path]}
        )
        if response.status_code not in (200, 204, 404):
            raise DomainError("Private file removal is pending", 503)

    def close(self):
        self.client.close()


class DurableFiles:
    def __init__(self, root, store, objects=None):
        self.root, self.store, self.objects = Path(root), store, objects

    def path(self, key):
        key = key.replace("\\", "/")
        parts = PurePosixPath(key)
        if parts.is_absolute() or ".." in parts.parts or not parts.parts or ":" in key:
            raise DomainError("Invalid stored file path", 400)
        path = (self.root / str(parts)).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise DomainError("Invalid stored file path", 400)
        return key, path

    @staticmethod
    def cache(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def write(self, key, data):
        key, path = self.path(key)
        sha = hashlib.sha256(data).hexdigest()
        if self.store.remote:
            with self.store.tx() as c:
                previous = c.execute(
                    "SELECT sha256,deleted FROM blob_files WHERE path=?", (key,)
                ).fetchone()
                if previous and previous["sha256"] != sha:
                    raise DomainError(
                        "Immutable file path already has different bytes", 409
                    )
                c.execute(
                    "INSERT INTO blob_files(path,sha256,size,data) VALUES(?,?,?,?) ON CONFLICT(path) DO UPDATE SET data=excluded.data,deleted=false WHERE blob_files.deleted=true",
                    (key, sha, len(data), data),
                )
                c.execute("SELECT pg_notify('zerowall_files','')")
        try:
            self.cache(path, data)
        except OSError:
            if not self.store.remote:
                raise
        return sha

    def read(self, key, sha):
        key, path = self.path(key)
        metadata = None
        if self.store.remote:
            with self.store.tx() as c:
                metadata = c.execute(
                    "SELECT sha256,size,deleted FROM blob_files WHERE path=?", (key,)
                ).fetchone()
            if not metadata or metadata["deleted"] or metadata["sha256"] != sha:
                raise DomainError("Stored file is missing or its manifest changed", 422)
        try:
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() == sha:
                return data
        except OSError:
            pass
        if not self.store.remote:
            raise DomainError(
                "Stored file is missing or failed its integrity check", 422
            )
        with self.store.tx() as c:
            staged = c.execute(
                "SELECT data FROM blob_files WHERE path=? AND deleted=false", (key,)
            ).fetchone()
        data = (
            bytes(staged[0])
            if staged and staged[0] is not None
            else self.objects.get(key)
        )
        if len(data) != metadata["size"] or hashlib.sha256(data).hexdigest() != sha:
            raise DomainError("Stored file integrity check failed", 422)
        try:
            self.cache(path, data)
        except OSError:
            pass
        return data

    def materialize(self, key, sha):
        data = self.read(key, sha)
        _, path = self.path(key)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            self.cache(path, data)
        return path

    def inventory(self, prefix):
        if self.store.remote:
            with self.store.tx() as c:
                return [
                    dict(row)
                    for row in c.execute(
                        "SELECT path,size FROM blob_files WHERE deleted=false AND path LIKE ?",
                        (prefix + "/%",),
                    )
                ]
        folder = self.root / prefix
        return [
            {"path": p.relative_to(self.root).as_posix(), "size": p.stat().st_size}
            for p in folder.iterdir()
            if p.is_file()
        ]

    def delete(self, key):
        key, path = self.path(key)
        if self.store.remote:
            with self.store.tx() as c:
                c.execute(
                    "UPDATE blob_files SET deleted=true,data=NULL WHERE path=?", (key,)
                )
                c.execute("SELECT pg_notify('zerowall_files','')")
        path.unlink(missing_ok=True)

    def flush(self, limit=4):
        if not self.store.remote:
            return 0
        with self.store.tx() as c:
            pending = [
                dict(row)
                for row in c.execute(
                    "SELECT path,sha256,data,deleted FROM blob_files WHERE data IS NOT NULL OR (deleted=true AND mirrored=true) ORDER BY path LIMIT ?",
                    (limit,),
                )
            ]
        for item in pending:
            if item["deleted"]:
                self.objects.delete(item["path"])
            else:
                self.objects.put(item["path"], bytes(item["data"]))
            with self.store.tx() as c:
                if item["deleted"]:
                    c.execute(
                        "UPDATE blob_files SET mirrored=false WHERE path=? AND deleted=true",
                        (item["path"],),
                    )
                else:
                    c.execute(
                        "UPDATE blob_files SET data=NULL,mirrored=true WHERE path=? AND sha256=?",
                        (item["path"], item["sha256"]),
                    )
        return len(pending)


class FileMirror:
    def __init__(self, files):
        self.files, self.stop = files, threading.Event()
        self.thread = None
        self.last_error = None
        self.wakeup = threading.Event()

    def wake(self):
        self.wakeup.set()

    def start(self):
        def loop():
            delay = 5
            while not self.stop.is_set():
                self.wakeup.clear()
                try:
                    pending = self.files.flush()
                    self.last_error = None
                    delay = 0.1 if pending else min(60, max(5, delay * 2))
                except Exception:  # noqa: BLE001 -- durable mirror boundary; no secret exception URLs in logs
                    self.last_error = (
                        "Private file mirroring deferred; bytes remain in Postgres"
                    )
                    delay = min(300, max(5, delay * 2))
                self.wakeup.wait(delay)

        self.thread = threading.Thread(
            target=loop, daemon=True, name="zerowall-file-mirror"
        )
        self.thread.start()

    def close(self):
        self.stop.set()
        self.wake()
        if self.thread:
            self.thread.join(timeout=35)
