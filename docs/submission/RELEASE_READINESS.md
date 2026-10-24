# ZeroWall release and hosting assessment

Assessed October 24, 2026, against the repository and [official rules](https://nebiusglobalaihackathon.devpost.com/rules). Publication, deployment and submission are not completed.

## Recommendation

Freeze the current council for a focused demonstration. Prepare a public repository and reproducible downloadable test build, and record the 2:50 video. The user selected **Vercel + Supabase** so the app can run while their computer is off. The opt-in code conversion is now implemented; deployment and the production ledger cutover remain pending. The rules accept a working demo, hosted application or test build, and define Token Factory use as a runtime inference call. The frontend need not be hosted on Nebius.

The chosen cloud shape is one Vercel container Service serving React/FastAPI, one Vercel Daemon running the council, and Supabase Postgres/private Storage. See the [runbook](../operations/VERCEL_SUPABASE.md). No paid host, subscription, GPU or additional payment is authorized. A labelled public replay can supplement the live app but cannot be presented as fresh execution.

## Readiness

| Area | Current evidence | Remaining work |
| --- | --- | --- |
| Council | Three-model Token Factory lineup, independent openings, review, synthesis, follow-ups, answer preservation | Choose and rehearse a complete genuine demo including a second turn |
| Tavily | Collective queries/search, deduplication, extraction, shared source snapshots, contributor attribution | Capture evidence from the same genuine council used in the video |
| UI | Simple/Explain, Compare, source/full-response inspection, usage totals, thinking/context controls | Recording readability check and release smoke test |
| Runtime | Local records show completed Token Factory calls for current models, including Nemotron | Export scrubbed receipts tied to the demo; never publish the private runtime database |
| Checks | Cloud conversion: 22 Linux/Postgres integration checks at 1 GiB, 75 targeted local regressions, 33 final API/streaming checks. Broad local run: 728 passes plus one stored-record/API-presentation assertion mismatch, corrected and covered by rerun. Earlier browser register: 28 cases | Actual Vercel/Supabase acceptance and public-browser checks; no claim that the final complete repository suite was rerun |
| Distribution | Source, lockfiles, MIT, setup and archive scripts | Publication audit, fresh build verification, first Git commit and remote; currently no commits or remote |
| Hosting | Vercel/Supabase adapters, private file outbox, separate worker ownership, migration inventory and Linux/Postgres integration checks; local mode retained | Set up the actual free accounts and verify TLS/proxy, private bucket, session pooler, ledger cutover and judge access; see [cloud operations](../operations/VERCEL_SUPABASE.md) |
| Submission | Current description, final checklist, 2:50 script | Actual repository/build/video links, example outcome, entrant confirmation and submitted entry |

## Hosting comparison

| Choice | Fit and decision |
| --- | --- |
| Public repository plus downloadable local test build | Accepted distribution format under the rules and preserves the architecture. Preferred zero-hosting-cost route. New model execution still needs valid, free judging access; don't assume judges buy credit |
| One persistent CPU service plus durable volume | Preferred live-host architecture if existing infrastructure/funding covers judging. Preserves worker ownership, SQLite and artifacts. Needs explicit remote authentication/configuration |
| Vercel Services/Daemon plus Supabase | Selected. Opt-in adapters, durable file outbox, separate executor, ledger cutover and deployment configuration implemented; actual Free account/beta availability and external acceptance checks are pending |
| Current executor inside Vercel Functions | Invocation duration limits do not directly fit a persistent lifespan worker. Avoid a direct port; a durable external worker/workflow redesign could make it viable later |
| Render Free with current SQLite/files | Sleeps on idle and loses local files on restart/spin-down. Avoid for the current live app; external durable persistence requires changes |
| Cloudflare Quick Tunnel | Changing hostname, no uptime guarantee, no SSE support; does not implement public app authorization. Development previews only |

References: [Vercel function limits](https://vercel.com/docs/functions/limitations), [Render Free persistence and sleep](https://render.com/docs/free), [Quick Tunnel limits](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/). Supabase has a [Free plan](https://supabase.com/docs/guides/platform/billing-on-supabase), but choosing it does not migrate this backend or supply its worker.

## Hosting work remaining

1. Configure the actual hostname, HTTPS origin, private Supabase project/bucket and server secrets using the [Vercel/Supabase runbook](../operations/VERCEL_SUPABASE.md). The current local setup remains operational until an explicit cutover.
2. Test the actual external access path. Hosted mode disables local auto-session entry even behind a loopback proxy; the real public host must be checked as well. Do not expose the access secret or the developer's private chats.
3. Choose a dedicated judge instance or isolate user state correctly. A public director session shares chats, controls and API budget. A general multi-user service needs more than a login screen.
4. Verify Postgres, private Storage, file mirroring and worker ownership on the real cloud host. Do not run independent copies of the spending ledger. SQLite remains the separate local default.
5. Preserve spending authority during migration: a clean database must not reset spent credit or unknown reservations. Keep the authorized $24 aggregate cap and $0 additional payment.
6. Configure server-side credentials; test actual proxy response updates, restart/recovery and external access. Do not assume local behavior proves public-host behavior.

These are deployment requirements, not a rewrite of the council. Submission preparation requires no change to answer length, reasoning settings, source retention or review behavior.

## Dates and funding

- Submit before **October 30, 2026, 10:00 PDT / 17:00 UTC / 19:00 Cairo**. Target October 29 for uploads and link checks.
- Official judging runs **December 1–15**, ending **December 15, 2026, 12:00 Pacific Time**. Free testing access must continue until judging ends. Private access needs credentials/testing instructions.
- Previously reported credit/trial dates do not establish December model availability. Confirm expiry and funded access without assuming or authorizing a paid refill.
- Hosting alone does not solve model funding or persistence; a downloadable build alone does not establish that judges can make paid requests for free. Document access honestly. Saved replay preserves evidence but must be identified as saved execution.

## Execution order

1. Select the real demo conversation and rehearse the [video script](DEMO_SCRIPT.md).
2. Audit the publication file set, refresh the archive and verify a fresh installation.
3. Publish reviewed source/test build with MIT detection, setup, current models and runtime evidence.
4. Complete the judging-access arrangement and any public-host work; check externally.
5. Record actual product footage, edit to 2:50, caption in English, upload as Public on YouTube.
6. Fill the [project description](PROJECT_DESCRIPTION.md), platform feedback and final links; finish the [checklist](FINAL_CHECKLIST.md).
