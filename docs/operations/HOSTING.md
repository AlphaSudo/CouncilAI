# Hosted council operations

The hosted mode is opt-in and intended for one private director/judging instance. It does not create a multi-user SaaS. Local mode remains the default and retains direct entry to the composer. No cloud resources or new spending authority are created by this configuration.

For the selected free cloud route, use the [Vercel and Supabase guide](VERCEL_SUPABASE.md) and [conversion checklist](../../plans/13_FREE_HOSTING.md). This page documents the separate volume-backed option; do not place that setup unchanged on an ephemeral disk.

## Deployment shape

Run one Linux container containing the built React UI, FastAPI and its executor. Mount one persistent local/block-backed volume at `/var/lib/zerowall`. Use one replica, with no additional Uvicorn workers or reload process. Place the service behind a host-managed HTTPS reverse proxy on the same public origin. The Compose example binds the application only to host loopback port 8080; the proxy supplies public TLS.

SQLite's database, WAL, journal, saved replies, source blobs, artifacts and budget records belong on the same durable volume. Do not use an ephemeral service filesystem or independently scaled database copies. Tokenizer files are checksum-verified during image construction and baked into the image separately from the mounted runtime data.

Reference architecture: [FastAPI containers](https://fastapi.tiangolo.com/deployment/docker/) and [Docker volume lifecycle](https://docs.docker.com/engine/storage/volumes/). A volume preserves data across container replacement; it is not an off-host backup.

## Configure and build

1. Copy `deploy/hosted.env.example` to ignored `.env.hosted` in the repository root.
2. Set the actual `ZEROWALL_PUBLIC_ORIGIN`, using HTTPS and no path. Generate a new random `ZEROWALL_DIRECTOR_TOKEN` of 32–200 ASCII characters without whitespace. Keep this access code private; supply it through the host's secrets system/testing instructions rather than public repository text.
3. Set only the provider keys needed for this instance, server-side. The image build excludes `.env*` and runtime data. It uses public dependency/tokenizer downloads, never model inference.
4. Provision and verify persistent storage on the selected host before setting `ZEROWALL_PERSISTENT_STORAGE_CONFIRMED=true`. This flag is an operator declaration; software cannot prove a provider's disk-retention policy.
5. Build and run one instance:

```text
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml up -d
```

Compose loads `.env.hosted`, mounts `council-data`, and sets hosted mode. Keep the same Compose project/volume identity on redeploy. Do not delete the data volume during deployment. Configure the actual platform's mount, port and healthcheck when deploying without Compose. `PORT` defaults to 8000; `ZEROWALL_DATA_DIR` must be absolute.

Build environments should have network access to the locked dependency registries and pinned public tokenizer URLs. A failed download or checksum mismatch stops the build rather than accepting a broken runtime image.

## Hosted behavior

- Startup refuses missing HTTPS origin, access secret, explicit data location or persistent-storage declaration. Runtime startup checks the built frontend, writable data directory, database integrity and configured model tokenizers.
- `GET /api/health` is liveness. `GET /api/ready` is readiness: frontend present, executor alive, and database query successful. Health probes do not make inference requests, refresh pricing or alter spending reservations.
- Anonymous visitors see the access-code form. Local auto-session entry is disabled even when a reverse proxy connects from loopback. Session cookies are Secure, HttpOnly and SameSite=Strict. Refreshing the page reuses the session instead of retrying local login.
- Only the configured public hostname and loopback healthcheck hosts are trusted. Mutation origins are compared to the explicit HTTPS origin, so TLS termination can use an internal HTTP hop without accepting arbitrary forwarded headers.
- `zerowall open` opens the configured HTTPS origin in hosted mode. The local CLI still binds to loopback by default; hosted mode binds to `0.0.0.0` inside the service/container.
- An empty instance starts without live spending authorization. Saving an API key alone does not unlock inference. Authentication and budget authorization remain separate.

All holders of this instance's director access code can inspect its chats and operate its controls. Do not expose the access code publicly, mount an unscrubbed personal database, or describe this as per-user isolation. A public visitor playground requires a separate access/data/budget design.

## Cutover, persistence and recovery

Do not run a local and hosted copy as independent spenders against the same $24 authority. Before enabling live requests, plan a single ledger cutover preserving already spent credit and unknown reservations, or provide a genuinely separate authorized funding arrangement. A clean deployment is deliberately locked and is not a fresh $24 grant.

Use the existing `scripts/backup.py` from the release source on a stopped/quiescent instance; its executor lock prevents an inconsistent database-plus-artifact archive. Keep backups outside the service volume and verify a restore. Restore intentionally clears live verification: it must not silently reauthorize provider dispatch. Review private chats and documents before transferring any developer data to a judge instance.

Container restart/replacement must retain the volume and access secret. Interrupted network attempts retain unknown charges; they must not be replayed just because the host restarted. Deploy during an idle window or explicitly pause, then verify recovery after startup. The Compose shutdown grace period is 90 seconds; it does not guarantee an upstream request will complete.

## Repeatable local deployment check

```text
podman build --format docker --tag localhost/zerowall:hosting-check .
python scripts/smoke_hosted_container.py --engine podman
```

Docker is also supported by passing `--engine docker` after building the same image tag. The smoke check creates only uniquely named temporary containers and a volume, then cleans them up. It exercises access boundaries, compiled assets, a complete scripted reviewed council, a second cycle, source upload, container replacement, saved-session/history/source retention, and the actual readiness healthcheck. It makes zero paid inference requests and records the tested source hashes and image ID.

`docs/validation/hosted-container.json` records the result. This is a real Linux container check with scripted model answers, not a cloud-host, real HTTPS-browser, or provider-latency certification.

## Public release checks still required

- [ ] Selected hosting plan, storage and service availability fit the $0 additional-payment rule and judging period.
- [ ] Public HTTPS domain and proxy are configured; external browser login, refresh/logout and session-cookie behavior work.
- [ ] Anonymous visitors cannot read chats, create model calls or acquire a local director session.
- [ ] The actual proxy delivers streaming/polling progress and supports a completed council plus same-chat follow-up.
- [ ] Actual host restart/redeploy preserves chats, source blobs, artifacts, reservations and the singleton worker contract.
- [ ] A coherent backup is restored and verified; a tested previous image can be redeployed against the preserved state.
- [ ] Private content is excluded or appropriately protected, secrets are replaced before publication, and a single cumulative budget is retained.
- [ ] Judge access and model funding remain valid through December 15, 2026.

Do not mark hosting complete solely because a local image builds or a platform displays a green deployment badge.
