# Vercel and Supabase deployment

The opt-in cloud implementation uses one Vercel container Service for the existing built React UI and FastAPI, one Vercel Daemon for council execution, and Supabase Postgres plus a private Storage bucket. Keeping the UI and API together retains the existing paths, cookies and access-code flow. Long model calls run in the Daemon, outside HTTP request lifetimes. Local mode still uses SQLite and local files.

Deployed on October 24, 2026 at [the production council](https://web-mu-weld-26.vercel.app). The container Service and one `council-worker` Daemon are running. Actual HTTPS health/readiness, hosted authentication, secure session persistence/logout, Supabase session-pooler connectivity, private bucket metadata and exclusive worker ownership passed. All 15 Production variables are configured. No model inference was dispatched during setup.

**Production activation:** the user explicitly requested a fresh $24 cloud cap on October 24, 2026 instead of importing local spending. The cloud ledger was initialized at zero committed usage with that new authorization. Local Token Factory inference was disabled atomically after confirming no queued/running requests; its old ledger and private conversations remain intact, with a verified local database backup. No private history was uploaded. Additional-payment authority remains $0. This was an explicit operator action, never an automatic allowance reset on deployment.

Two synthetic hosted review cycles, original-response access, export download, live event delivery and an actual private Storage upload/download hash check passed. Two real Super/Beam/DeepSeek review cycles with collective search also completed in the same chat. All originals remained readable, earlier messages were unchanged and there were no unknown outcomes. See [production acceptance](PRODUCTION_ACCEPTANCE.md) for scope, usage and replacement-deployment verification; no paid hosting subscription was used.

## Free accounts and platform gate

Create Vercel Hobby and Supabase Free accounts. In Vercel, confirm Services and Daemons are available for this project before deploying. They are beta features. Hobby Daemons currently include five active CPU hours per month and stop when that allowance is exhausted. Waiting does not count as active CPU; tokenization, parsing and other work does. The daemon configuration requests one 1 GiB instance. There is no promise that every workload fits the free quota. Do not upgrade plans or enable paid add-ons. [Services](https://vercel.com/docs/services), [Daemon limits](https://vercel.com/docs/daemons/limits)

Supabase Free has finite database/storage/egress allowances and may pause an inactive project. Check dashboard usage before the demo and during judging. Do not use artificial keepalive traffic to evade plan policies. [Free plan limits](https://supabase.com/docs/guides/platform/billing-on-supabase), [free project pausing](https://supabase.com/docs/guides/platform/free-project-pausing)

## Supabase setup

1. Create one Free project. Retain its database password privately.
2. Create a **private** bucket called `zerowall-private`; do not enable Public access or anonymous upload policies. The server uses the secret/service-role key; the browser receives neither this key nor the database URL.
3. From **Connect**, copy the IPv4-compatible **session pooler** connection string on port **5432**. URL-encode special password characters and require TLS with `sslmode=require`. Do not use transaction-pooler port 6543: worker ownership, notifications and idempotency locks require session affinity. [Connection options](https://supabase.com/docs/guides/database/connecting-to-postgres)
4. Use a dedicated project/database for this application. The application creates its private `zerowall` schema and revokes PUBLIC schema access. Do not add this schema to Supabase's exposed API schemas. The normal database owner credentials need schema/table/index creation privileges on first startup.

Files first enter a durable Postgres outbox with their manifest and hash, then the worker mirrors them to private Storage. An interrupted Storage upload is retried by comparing immutable bytes; this never retries model inference. Until mirroring succeeds, bytes remain in the database. An extended Storage outage can consume database space; restore Storage access before the Free database fills. No replies are shortened or deleted to fit a quota.

## Configure secrets

Use [the environment template](../../deploy/vercel.env.example). Set these in **Vercel Production only**: `ZEROWALL_MODE`, `ZEROWALL_STORAGE`, `ZEROWALL_ROLE`, `ZEROWALL_DATA_DIR`, `ZEROWALL_PUBLIC_ORIGIN`, `ZEROWALL_DIRECTOR_TOKEN`, `ZEROWALL_DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `ZEROWALL_STORAGE_BUCKET`, `NEBIUS_API_KEY`, `TAVILY_API_KEY`, and the two provider-disable flags shown there. The service/daemon commands override their process role explicitly. Keep secrets out of Preview and Development deployments; previews must not connect to the production queue or budget.

Generate a fresh random director access code of 32–200 ASCII characters without whitespace. The same code across redeploys preserves sessions. The app is one private director instance, not a multi-user public playground. Anyone with that code can see its shared history and sources.

`ZEROWALL_DATA_DIR=/tmp/zerowall` is only a disposable cache in Supabase mode. Do **not** set `ZEROWALL_PERSISTENT_STORAGE_CONFIRMED=true`; that declaration is for the older volume-backed deployment. Missing/broken remote credentials fail closed and never create a fallback SQLite ledger.

## Spending-ledger cutover

By default, a new cloud database grants **no allowance**. Import the existing ledger to retain the old aggregate spending scope. The current production instance instead uses the user's separately and explicitly authorized fresh $24 cloud cap described above. Do not repeat that initialization on redeploy, import the old reservations into this new scope, or re-enable the old local authority. No migration or publication of the developer's history happens automatically.

1. Inspect an inventory without changing any data:

   ```powershell
   .\.venv\Scripts\python.exe -m zerowall.cloud_migration --source 'C:\Java Developer\nvidia\data'
   ```

2. Finish, pause or stop active councils, then stop the local server. Keep a verified backup using the existing backup procedure. The migration refuses to run while an executor owns the directory, while jobs are queued/running, or while dispatched requests remain unresolved as `reserved`.
3. Load the cloud template into your shell environment privately, using an **absolute Windows temporary directory** for `ZEROWALL_DATA_DIR` while running migration from Windows. `.env.cloud` is ignored but is not automatically loaded: use your secret manager or explicit environment loading; never replace the local `.env.local` as a shortcut.
4. Import to an empty destination:

   ```powershell
   .\.venv\Scripts\python.exe -m zerowall.cloud_migration --source 'C:\Java Developer\nvidia\data' --apply
   ```

   The default copies the ledger and settings without private chats/documents. Add `--include-history` only when those personal materials are intentionally approved for the private cloud instance. Both modes preserve settled, held and unknown monetary amounts. The source is retained; its live authorization is disabled before import. The destination stays locked for explicit reauthorization. If transfer fails, retry against an empty destination; neither side is silently reauthorized. Do not reauthorize an independent local copy after cloud cutover.
5. Verify `cloud_ledger_ready`, aggregate committed amounts and unknown reservations before authorizing the existing credit in the deployed instance. The provider keys themselves never unlock spending. The absolute cap remains $24, including prior usage, with $0 additional payment authorized.

There is no automatic reverse migration. Before rolling back from cloud to local, stop the daemon and reconcile the latest remote ledger. Re-enabling an old local backup would lose cloud spending information.

## Vercel setup

1. Push the reviewed source to a GitHub repository. `.env*`, runtime data, caches and `.vercel` are excluded. Run the source packaging/credential scan before publication.
2. Import that repository in Vercel. Set the **project root to the repository root**, not `apps/web`. Use the root `vercel.json`, which defines the container Service and one Daemon. Do not enable extra replicas or a second project worker.
3. Set the Production environment variables above and the final included `*.vercel.app` HTTPS origin. Keep preview deployments disconnected from production data and provider keys. Select the daemon region near the Supabase region; `iad1` is the supplied default and can be changed before deployment.
4. Deploy. The Docker build installs locked dependencies, compiles React and verifies public model tokenizer downloads. It does not include `.env.local` or runtime data and does not call model APIs.
5. Confirm the Service and Daemon logs show successful startup without printing secrets. A rolling deployment waits for the old worker's database ownership lock; only the owner recovers/claims jobs. The daemon has a one-hour termination grace period to drain an active cycle. A crash still retains unknown charges and never automatically replays an uncertain paid request.

The API role does not execute jobs or perform restart recovery. Idle worker waits use Postgres LISTEN/NOTIFY with a maximum sixty-second reconciliation interval; job notifications wake immediately and scheduled retry deadlines shorten that interval. File changes also send notifications, while an idle file mirror backs off to sixty seconds. Active answers retain their ownership checks. SSE responses end before the API request ceiling; the browser reconnects with its saved event sequence while the worker continues. See [judging availability](JUDGING_AVAILABILITY.md) for cloud schedules, worker CPU observations and recovery.

Large chat/original-response JSON and ZIP downloads are streamed in full rather than sent as one buffered body. This addresses the documented 4.5 MB buffered-response limit without truncating model output. Real deployment must still verify streaming through Vercel's proxy. [Vercel response-size guidance](https://vercel.com/kb/guide/how-to-bypass-vercel-body-size-limit-serverless-functions)

`zerowall doctor` reports the selected backend, whether the ledger was imported, whether a worker owns the queue, pending file count/bytes, and the aggregate budget. It never makes an inference request. A growing pending-file queue indicates that private Storage access/quota needs attention.

For a repeatable local Linux check, start a **disposable** Postgres 17 container with port `127.0.0.1:55432`, user/database `postgres`, and synthetic password `local-test-only`; build `localhost/zerowall:vercel-check` with `podman build --format docker --tag localhost/zerowall:vercel-check .`, then run `python scripts/check_cloud_container.py`. The integration fixtures clear the test database's `zerowall` schema. Never point them at the live application database. The script checks source hashes and writes `docs/validation/cloud-container.json`.

## Acceptance checks on the real deployment

- Anonymous HTTPS visitors see the code form; loopback proxy traffic cannot auto-login. Confirm secure session cookies, refresh and logout.
- Check `/api/ready` for the API and verify the Daemon is running separately. API readiness alone does not certify worker availability or remaining Hobby CPU quota.
- Run a scripted/demo council first, then a second turn in the same chat. Upload a source; inspect search hits, original responses and an exported review pack.
- Replace the Service and Daemon, then verify the same history, source bytes, originals and ledger. Check unknown paid attempts remain counted and un-replayed.
- Only after cutover verification, authorize a small live test under the existing $24 aggregate cap. Check provider availability, Tavily search, latency and actual dashboard usage. No such live test is part of the offline conversion.

Actual Vercel build/routing, Supabase TLS/session pooling, private bucket metadata and public HTTPS authentication passed on October 24, 2026. Actual Storage blob round trips, live event streaming, two synthetic cycles and two real cycles with collective search passed. The user explicitly chose a fresh $24 cloud cap instead of a ledger import. See [production acceptance](PRODUCTION_ACCEPTANCE.md) for replacement-deployment checks and remaining release work. Local container tests cover these implementation paths but do not substitute for the remaining hosted checks.
