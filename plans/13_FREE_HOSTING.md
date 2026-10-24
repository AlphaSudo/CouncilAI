# Free hosting decision and conversion checklist

Researched October 24, 2026. **Status: Vercel/Supabase production deployment is running; a fresh $24 cloud cap is active under explicit user authorization; two synthetic and two real hosted council cycles passed.** Local SQLite remains the default. See the [deployment runbook](../docs/operations/VERCEL_SUPABASE.md) and [environment template](../deploy/vercel.env.example).

The user chose **Vercel + Supabase** after the comparison. See [Render versus Vercel](../docs/operations/FREE_HOSTING_COMPARISON.md), including current quotas and a real 512 MiB startup probe. Account setup, actual container deployment, HTTPS authentication and worker ownership checks passed. Two synthetic hosted cycles, original replies, exports, event delivery and an actual private Storage blob round trip passed. The user explicitly chose a fresh $24 cloud allowance, with local paid inference disabled; two real same-chat cycles with collective search also passed. See [production acceptance](../docs/operations/PRODUCTION_ACCEPTANCE.md) for replacement-deployment checks.

## Preferred cloud route: Vercel and Supabase

Use **Vercel for the React frontend, Python API service and a dedicated council worker**, plus **Supabase Free for Postgres and a private Storage bucket**. The React build and API share one container Service and origin; the Daemon is separate. The already selected Token Factory and Tavily APIs remain the inference and search providers.

Correction after checking Vercel's current documentation: Vercel supports Python/FastAPI Services and long-running container Daemons, including on Hobby within quotas. These features are in beta; Services retain function duration limits, while the continuous queue consumer belongs in a Daemon. The earlier recommendation treated ordinary Vercel Functions as the only execution option. Render is an alternative, not a required third host. [Vercel Services](https://vercel.com/docs/services), [Daemons](https://vercel.com/docs/daemons), [daemon limits](https://vercel.com/docs/daemons/limits)

The current single process combines API serving and worker execution. For Vercel, separate these entrypoints, share durable queue/state through Supabase, and ensure API service instances never each start their own executor. Keep a single worker with deployment-safe ownership. Verify actual Hobby eligibility, beta availability and included quotas before making this the final deployment target; no paid upgrade is authorized.

**Alternative:** Render Free can serve the existing FastAPI service and built React frontend together, with the same Supabase persistence conversion. This keeps the executor in the application service but has the sleep/startup limits below. Do not create both hosting stacks by default.

This is a way to target $0 hosting within free allowances, not an uptime or unlimited-usage promise. Keep accounts on their free plans without enabling paid upgrades. API inference continues to use the existing authorized Token Factory credit and the $24 aggregate cap; free hosting does not make inference free.

Neither ephemeral Vercel runtime storage nor Render's free filesystem can hold the authoritative chat database or source files. Move these to durable remote services before deployment. Do not satisfy the hosted startup check by falsely declaring temporary storage persistent.

The verified service trade-offs are:

- Render Free sleeps after 15 idle minutes and takes roughly a minute to wake. Free services may restart. Render also applies usage/outbound-traffic limits; without a payment method it suspends services rather than billing supplementary usage. [Render Free](https://render.com/docs/free)
- Supabase Free includes a 500 MB database and 1 GB of file storage. Its free project can pause after low activity over seven days, so judge-access planning must account for that. [Supabase billing](https://supabase.com/docs/guides/platform/billing-on-supabase), [project pausing](https://supabase.com/docs/guides/platform/free-project-pausing)
- Do not replace this with Render's free Postgres: it expires after 30 days, before the end of this hackathon's judging period. [Render Free database limits](https://render.com/docs/free)

Use the providers' included hostname and HTTPS; no purchased domain is needed. Do not use external pings solely to evade a provider's sleep policy or describe a sleeping free service as always on.

## Zero-migration alternative

If the developer computer can remain online, **Tailscale Funnel** supplies a public HTTPS URL pointing to its running council. Funnel is available on all plans; the Personal plan is free for eligible personal/non-commercial use. The computer, app and internet connection must remain available. This is self-hosting rather than independent cloud hosting. [Funnel](https://tailscale.com/docs/features/tailscale-funnel), [Personal plan](https://tailscale.com/pricing)

Use the existing explicit hosted access behavior before exposing any endpoint. Do not tunnel the current local auto-login server directly. Source/history access and the director code remain private. Tailscale installation/account sign-in, Funnel enablement and testing of the real URL are still required; none has been performed.

## Conversion implementation

### 1. Database and transaction semantics

- [x] Add an opt-in remote database configuration; preserve SQLite as the local default.
- [x] Port schema and direct SQL to Postgres deliberately. Preserve record IDs, ordering, event sequence, idempotency, source versions, job states and financial amounts.
- [x] Preserve atomic reservation/dispatch admission and unknown-charge retention. Protect concurrent API mutations; do not weaken transaction isolation to make a driver fit.
- [x] Verify actual Supabase IPv4 Session pooler on port 5432 with TLS, schema creation and exclusive Daemon ownership. Worker ownership uses session affinity rather than transaction pooling. [Connection options](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [x] Move readiness and startup checks behind the storage interface so they query the remote authority, never create a new local ledger as fallback.
- [x] Keep credentials server-side. A remote outage must never activate fixture replies as if they were live models or silently create an empty chat store.

### 2. Source and public-response persistence

- [x] Add a private object-storage adapter for source bytes, extracted documents, provider artifacts and generated exports. Local files become a disposable cache.
- [x] Preserve content hashes, immutable versions and read receipts; verify downloaded bytes after a cold start.
- [x] Inventory all direct filesystem reads/writes, including originals, transcripts, review packs and replay paths. Do not migrate uploads alone and leave original replies behind.
- [x] Preserve the answer-first order: public output must become durable before optional review annotations can fail.
- [x] Handle quota/storage failures explicitly while preserving already saved public text and charged attempts. Do not delete history or cap responses merely to fit a free tier.

### 3. Executor and reconnect behavior

- [x] Replace the per-machine lock with ownership coordinated through the remote authority. Handle overlapping old/new deployments without two workers dispatching the same work.
- [x] Recover jobs after a cold start without replaying an unknown paid request.
- [ ] Retain the browser's existing session/draft and show honest reconnect/waking progress. Keep the current same-origin access-code flow.
- [ ] Verify the actual free host's memory limit, startup time and tokenizer footprint using the built image. Optimize caches if necessary; do not lower the 262,144 context setting or remove thinking controls as a shortcut.
- [x] Keep free-service resource use bounded, including notification-based idle worker waits, bounded SSE requests and file-mirror backoff. Real dashboard quota monitoring remains required.

### 4. Migration and deployment

- [x] Prepare a dry-run migration with a complete record/blob inventory and hashes. No production migration has been run.
- [x] Preserve the same aggregate spent/held/unknown amounts. Migration disables the old authority first; cloud dispatch requires a ledger-import marker and explicit reauthorization. No new $24 allowance is created.
- [x] Exclude private personal chats/documents from a judge instance unless explicitly intended. Migration defaults to ledger/settings only; history requires an explicit option. A shared director code is not multi-user isolation.
- [x] Deploy the root container configuration on Vercel Hobby: one web Service and one council-worker Daemon in iad1. Production health/readiness and worker ownership passed; no paid upgrade or custom-domain purchase.
- [x] Document exact Free account setup and server-secret names, including private-bucket access. All 15 Production settings are saved; actual deployment passed its initial health/authentication checks. No purchase was made.
- [x] Verify actual HTTPS login/refresh/logout, collective search, complete answers, all originals, source import/export and two same-chat real review cycles. See [production acceptance](../docs/operations/PRODUCTION_ACCEPTANCE.md).

## Acceptance gates

- [x] Existing local mode still passes its relevant regression suite: 75 targeted regressions. The broad run had 728 passes and one presentation-versus-storage assertion mismatch, corrected and covered by the targeted rerun.
- [x] Real Postgres integration tests cover transaction rollback, ordering, idempotent API operations and concurrent admission.
- [x] Storage adapter tests with an HTTP transport double cover upload, cache removal, re-download, integrity mismatch and unavailable responses. Actual Supabase server-key access and private bucket metadata passed; actual uploaded blob download/hash checks also passed.
- [x] Two successive scripted council cycles survive destruction of API-local runtime files and creation of a replacement instance.
- [x] Chat/source/export persistence, original public replies and monetary reservations are covered by integration tests.
- [x] Unknown charged requests remain counted and are not automatically retried.
- [ ] Host memory/startup tests pass at the actual Free resource limits.
- [ ] Actual Vercel Hobby (or Render Free) and Supabase Free accounts/quotas are verified; model-credit availability covers judging through December 15, 2026.

The [cloud container report](../docs/validation/cloud-container.json) records 24 passing integration checks in the Linux image at a 1 GiB limit, a real temporary Postgres 17 database, a Storage HTTP transport double and matching application source hashes. This includes complete large-response streaming, new/legacy Supabase key headers and the actual background executor wake/ownership path. The actual private bucket metadata, Vercel container deployment, HTTPS authentication and worker ownership passed. Actual blob round trips, streamed event delivery and two real same-chat councils passed. The user explicitly authorized the new cloud cap instead of a ledger import; replacement-deployment verification is recorded in [production acceptance](../docs/operations/PRODUCTION_ACCEPTANCE.md).

## Information needed to activate the cloud route

The preferred route needs Vercel Hobby and Supabase Free accounts, one Supabase project and a private bucket. Render is needed only if the alternative is chosen. Exact host and server-secret configuration comes after the adapters and migration are ready. Save credentials in ignored environment files/provider secrets, not in chat or frontend code. No additional GPU, OpenRouter or LangSmith account is required.

The user confirmed the app must work while the developer computer is off, and selected Vercel + Supabase. External credentials and initial deployment are complete. The user explicitly authorized a fresh $24 cloud ledger rather than transferring prior spending. Local paid inference is disabled and its private history is retained. Two real same-chat cycles with collective search passed. See [production acceptance](../docs/operations/PRODUCTION_ACCEPTANCE.md) for replacement-deployment verification.
