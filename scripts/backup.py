"""Stop the server before backup/restore for a coherent DB + artifact snapshot."""

import argparse, hashlib, json, sqlite3, zipfile, tempfile
from pathlib import Path
from contextlib import closing
from zerowall.settings import Settings
from zerowall.process_lock import ProcessLock


def backup(destination, settings):
    lock = ProcessLock(settings.data / "executor.lock")
    lock.acquire()
    try:
        files = {}
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "zerowall.sqlite3"
            with (
                closing(sqlite3.connect(settings.data / "zerowall.sqlite3")) as src,
                closing(sqlite3.connect(database)) as dst,
            ):
                src.backup(dst)
            files["zerowall.sqlite3"] = database.read_bytes()
            for directory in ("artifacts", "exports", "review-exports", "source-blobs"):
                if (settings.data / directory).exists():
                    for path in (settings.data / directory).rglob("*"):
                        if path.is_file():
                            files[
                                str(path.relative_to(settings.data)).replace("\\", "/")
                            ] = path.read_bytes()
        inventory = {
            name: hashlib.sha256(content).hexdigest() for name, content in files.items()
        }
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as z:
            for name, content in files.items():
                z.writestr(name, content)
            z.writestr("backup-manifest.json", json.dumps(inventory))
        return {"files": len(files), "credential_files_included": False}
    finally:
        lock.release()


def restore(archive, destination):
    dest = Path(destination).resolve()
    if dest.exists() and any(dest.iterdir()):
        raise ValueError("Restore destination must be empty")
    with zipfile.ZipFile(archive) as z:
        inventory = json.loads(z.read("backup-manifest.json"))
        if set(z.namelist()) != set(inventory) | {"backup-manifest.json"}:
            raise ValueError("Backup inventory mismatch")
        if sum(i.file_size for i in z.infolist()) > 500_000_000:
            raise ValueError("Backup exceeds size limit")
        for name, sha in inventory.items():
            target = (dest / name).resolve()
            if not target.is_relative_to(dest) or ":" in name or "\\" in name:
                raise ValueError("Unsafe backup path")
            if hashlib.sha256(z.read(name)).hexdigest() != sha:
                raise ValueError("Backup checksum mismatch")
        dest.mkdir(parents=True, exist_ok=True)
        for name in inventory:
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(name))
    # Billing verification is intentionally cleared: restore must not reauthorize paid work.
    with closing(sqlite3.connect(dest / "zerowall.sqlite3")) as c:
        c.execute("DELETE FROM settings WHERE key='live_verification'")
        c.commit()
    return {
        "restored": len(inventory),
        "live_dispatch_locked": True,
        "director_token": "generated at next startup",
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["create", "restore"])
    p.add_argument("archive")
    p.add_argument("--destination")
    a = p.parse_args()
    if a.command == "restore" and not a.destination:
        p.error("--destination is required for restore")
    print(
        json.dumps(
            backup(a.archive, Settings())
            if a.command == "create"
            else restore(a.archive, a.destination),
            indent=2,
        )
    )
