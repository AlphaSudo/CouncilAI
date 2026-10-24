"""Exercise a real Linux image without credentials, network inference or publication.

Creates only uniquely named temporary containers/volume, removes those in finally,
and never touches the developer's data directory or existing containers.
"""

import argparse
import base64
import hashlib
import json
import re
import secrets
import subprocess
import tempfile
import time
import uuid
from contextlib import closing
from pathlib import Path

import httpx


def smoke(engine, image):
    prefix = "zerowall-hosting-smoke-" + uuid.uuid4().hex[:12]
    volume = prefix + "-data"
    containers = []
    checks = []

    def command(*args, check=True):
        result = subprocess.run(
            [engine, *args], capture_output=True, text=True, timeout=120, check=False
        )
        if check and result.returncode:
            raise RuntimeError(
                f"Container command {args[0]} failed; inspect the local engine. No credentials printed."
            )
        return result.stdout.strip()

    def start(name, env_file):
        containers.append(name)
        command(
            "run",
            "--detach",
            "--name",
            name,
            "--env-file",
            str(env_file),
            "--mount",
            f"type=volume,source={volume},target=/var/lib/zerowall",
            "--publish",
            "127.0.0.1::8000",
            image,
        )
        port = command("port", name, "8000/tcp").rsplit(":", 1)[1]
        client = httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            trust_env=False,
            headers={
                "Host": "council.example",
                "Origin": "https://council.example",
                "X-ZeroWall-Director": "1",
            },
            timeout=10,
        )
        for _ in range(90):
            try:
                if client.get("/api/ready").status_code == 200:
                    return client
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        client.close()
        raise RuntimeError(
            "Container did not become ready. No live inference was enabled."
        )

    def post(client, path, body):
        response = client.post(
            path, json=body, headers={"Idempotency-Key": str(uuid.uuid4())}
        )
        if response.status_code != 200:
            raise AssertionError(f"{path} returned {response.status_code}")
        return response.json()

    def login(client, token):
        response = client.post("/api/session", json={"token": token})
        assert response.status_code == 200
        assert "Secure" in response.headers["set-cookie"]
        # Simulate TLS termination on the app's HTTP hop. A real public HTTPS
        # browser/proxy check remains required on the selected host.
        client.headers["Cookie"] = "zw_session=" + response.cookies["zw_session"]

    def completed(client, cid):
        for _ in range(100):
            value = client.get("/api/chats/" + cid).json()
            if value["chat"]["status"] in (
                "completed",
                "awaiting_director",
                "accepted",
            ):
                return value
            if value["chat"]["status"] in ("failed", "cancelled"):
                raise AssertionError(
                    "Fixture council failed inside hosted Linux container"
                )
            time.sleep(0.2)
        raise AssertionError("Fixture council did not finish")

    def transcript(value):
        return hashlib.sha256(
            json.dumps(value["messages"], sort_keys=True).encode()
        ).hexdigest()

    command("volume", "create", volume)
    try:
        with tempfile.TemporaryDirectory(prefix=prefix) as temporary:
            env_file = Path(temporary) / "runtime.env"
            token = secrets.token_urlsafe(40)
            env_file.write_text(
                "\n".join(
                    [
                        "ZEROWALL_MODE=hosted",
                        "ZEROWALL_PUBLIC_ORIGIN=https://council.example",
                        "ZEROWALL_DIRECTOR_TOKEN=" + token,
                        "ZEROWALL_DATA_DIR=/var/lib/zerowall",
                        "ZEROWALL_PERSISTENT_STORAGE_CONFIRMED=true",
                        "PORT=8000",
                        "NEBIUS_API_KEY=",
                        "TAVILY_API_KEY=",
                        "ZEROWALL_OPENROUTER_ENABLED=false",
                        "ZEROWALL_DIRECT_FREE_CONFIRMED=false",
                    ]
                ),
                encoding="utf-8",
            )
            first_name = prefix + "-first"
            with closing(start(first_name, env_file)) as client:
                assert client.get("/api/session").json() == {
                    "authenticated": False,
                    "local_entry": False,
                }
                assert client.get("/api/chats/bootstrap").status_code == 401
                assert client.post("/api/session/local", json={}).status_code == 403
                checks.append("no anonymous or loopback-proxy director session")
                html = client.get("/").text
                assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', html)
                assert assets and all(
                    client.get(asset).status_code == 200 for asset in assets
                )
                checks.append("built frontend and assets served")
                login(client, token)
                bootstrap = client.get("/api/chats/bootstrap").json()
                assert not bootstrap["providers"]["nebius_token_factory"]["ready"]
                checks.append("new instance does not inherit spending authority")
                value = post(
                    client,
                    "/api/chats",
                    {
                        "prompt": "Compare safe approaches to hosting a model council.",
                        "provider": "fixture",
                        "models": ["demo/analyst", "demo/critic", "demo/builder"],
                        "search_web": False,
                    },
                )
                cid = value["chat"]["id"]
                first = completed(client, cid)
                assert any(
                    message.get("phase") == "synthesis" for message in first["messages"]
                )
                checks.append("complete reviewed council in Linux")
                post(
                    client,
                    f"/api/chats/{cid}/library/import",
                    {
                        "title": "hosting-check-note.md",
                        "mime": "text/markdown",
                        "base64_content": base64.b64encode(
                            b"# Hosting check\nKeep SQLite and sources on the persistent volume."
                        ).decode(),
                    },
                )
                post(
                    client,
                    f"/api/chats/{cid}/messages",
                    {"text": "Keep the same chat and revise for durable storage."},
                )
                second = completed(client, cid)
                assert len(second["messages"]) > len(first["messages"])
                assert (
                    sum(m.get("phase") == "synthesis" for m in second["messages"]) >= 2
                )
                checks.append("second full review cycle in the same chat")
                saved_hash = transcript(second)
                saved_cookie = client.headers["Cookie"]
            command("stop", "--time", "10", first_name)
            command("rm", first_name)
            with closing(start(prefix + "-replacement", env_file)) as replacement:
                replacement.headers["Cookie"] = saved_cookie
                assert replacement.get("/api/session").json()["authenticated"] is True
                saved = replacement.get("/api/chats/" + cid).json()
                assert transcript(saved) == saved_hash
                checks.append(
                    "container replacement preserves all messages and authenticated session"
                )
                library = replacement.get(f"/api/chats/{cid}/library").json()
                assert "hosting-check-note.md" in json.dumps(library)
                checks.append("uploaded source library survives container replacement")
                # Prove the volume contains artifacts as well as SQLite, and no
                # model attempt or financial reservation was created by fixtures.
                proof = command(
                    "exec",
                    prefix + "-replacement",
                    "python",
                    "-c",
                    "import sqlite3,json,pathlib; p=pathlib.Path('/var/lib/zerowall'); c=sqlite3.connect(p/'zerowall.sqlite3'); "
                    "print(json.dumps({'reservations':c.execute('SELECT COUNT(*) FROM reservations').fetchone()[0],"
                    "'artifacts':sum(x.is_file() for x in (p/'artifacts').rglob('*')),"
                    "'source_blobs':sum(x.is_file() for x in (p/'source-blobs').rglob('*'))}))",
                )
                proof = json.loads(proof)
                assert proof["reservations"] == 0
                assert proof["source_blobs"] > 0
                checks.append("zero billed inference or spending reservations")
                code_files = ("api.py", "settings.py", "hosting.py", "cli.py")
                hashes = json.loads(
                    command(
                        "exec",
                        prefix + "-replacement",
                        "python",
                        "-c",
                        "import hashlib,json,pathlib; p=pathlib.Path('/app/src/zerowall'); "
                        f"print(json.dumps({{n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in {code_files!r}}}))",
                    )
                )
                local_root = Path(__file__).resolve().parents[1] / "src/zerowall"
                assert all(
                    hashlib.sha256((local_root / name).read_bytes()).hexdigest() == sha
                    for name, sha in hashes.items()
                )
                checks.append("tested image matches current hosting source")
                command("healthcheck", "run", prefix + "-replacement")
                checks.append("container readiness healthcheck succeeds")
                return {
                    "status": "passed",
                    "image": image,
                    "image_id": command(
                        "image", "inspect", image, "--format", "{{.Id}}"
                    ),
                    "hosting_source_sha256": hashes,
                    "checks": checks,
                    "persistent_artifact_files": proof["artifacts"],
                    "persistent_source_files": proof["source_blobs"],
                    "paid_calls": 0,
                    "public_host_verified": False,
                    "real_tls_browser_verified": False,
                }
    finally:
        for name in containers:
            command("rm", "--force", name, check=False)
        command("volume", "rm", volume, check=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default="podman")
    parser.add_argument("--image", default="localhost/zerowall:hosting-check")
    parser.add_argument("--output", default="docs/validation/hosted-container.json")
    args = parser.parse_args()
    result = smoke(args.engine, args.image)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
