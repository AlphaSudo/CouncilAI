# ZeroWall release and hosting assessment

Assessed October 24, 2026, against the repository and [official rules](https://nebiusglobalaihackathon.devpost.com/rules). Reviewed source is published at [AlphaSudo/CouncilAI](https://github.com/AlphaSudo/CouncilAI), initially at commit `e5b3d98`. The initial Vercel/Supabase deployment is running; two real same-chat council cycles with collective search passed under an explicitly authorized fresh $24 cloud cap. Hackathon submission remains incomplete.

## Recommendation

Freeze the current council for a focused demonstration. Prepare a public repository and reproducible downloadable test build, and record the 2:50 video. The user selected **Vercel + Supabase** so the app can run while their computer is off. The opt-in cloud conversion is deployed. HTTPS health/readiness, login/session/logout, private bucket metadata and worker ownership passed; two synthetic and two real same-chat review cycles with collective search, original-response access and private Storage round trips also passed. Local paid inference is disabled; the user explicitly chose a fresh $24 cloud cap instead of importing prior spending. See [production acceptance](../operations/PRODUCTION_ACCEPTANCE.md). The rules accept a working demo, hosted application or test build, and define Token Factory use as a runtime inference call. The frontend need not be hosted on Nebius.

The chosen cloud shape is one Vercel container Service serving React/FastAPI, one Vercel Daemon running the council, and Supabase Postgres/private Storage. See the [runbook](../operations/VERCEL_SUPABASE.md). No paid host, subscription, GPU or additional payment is authorized. A labelled public replay can supplement the live app but cannot be presented as fresh execution.

## Readiness

| Area | Current evidence | Remaining work |
| --- | --- | --- |
| Council | Three-model Token Factory lineup, independent openings, review, synthesis, follow-ups, answer preservation | Choose and rehearse a complete genuine demo including a second turn |
| Tavily | Collective queries/search, deduplication, extraction, shared source snapshots, contributor attribution | Capture evidence from the same genuine council used in the video |
| UI | Simple/Explain, Compare, source/full-response inspection, usage totals, thinking/context controls | Recording readability check and release smoke test |
| Runtime | Local records show completed Token Factory calls for current models, including Nemotron | Export scrubbed receipts tied to the demo; never publish the private runtime database |
| Checks | Cloud conversion: 24 Linux/Postgres integration checks at 1 GiB, 75 targeted local regressions, 33 final API/streaming checks. Broad local run: 728 passes plus one stored-record/API-presentation assertion mismatch, corrected and covered by rerun. Earlier browser register: 28 cases | Hosted acceptance now includes two synthetic and two real same-chat cycles, original replies, search and Storage; no claim that the final complete repository suite was rerun |
| Distribution | Reviewed source, lockfiles, MIT, setup and archive scripts published on `main`; exact index bytes passed the configured-secret and credential-pattern audit. Local data, secrets and internal validation traces excluded | Fresh-clone installation check, audited downloadable build and final demo receipts |
| Hosting | Vercel/Supabase adapters, private file outbox, separate worker ownership, migration inventory and Linux/Postgres integration checks; local mode retained | Initial hosted flow passed. Finish judge-access/funding arrangements and monitor free quotas; see [production acceptance](../operations/PRODUCTION_ACCEPTANCE.md) |
| Submission | Current description, final checklist, 2:50 script | Actual repository/build/video links, example outcome, entrant confirmation and submitted entry |

## Hosting comparison

| Choice | Fit and decision |
| --- | --- |
| Public repository plus downloadable local test build | Accepted distribution format under the rules and preserves the architecture. Preferred zero-hosting-cost route. New model execution still needs valid, free judging access; don't assume judges buy credit |
| One persistent CPU service plus durable volume | Preferred live-host architecture if existing infrastructure/funding covers judging. Preserves worker ownership, SQLite and artifacts. Needs explicit remote authentication/configuration |
| Vercel Services/Daemon plus Supabase | Selected. Opt-in adapters, durable file outbox, separate executor, ledger cutover and deployment configuration implemented; actual Hobby deployment and initial hosted acceptance passed, including two real same-chat cycles with search |
| Current executor inside Vercel Functions | Invocation duration limits do not directly fit a persistent lifespan worker. Avoid a direct port; a durable external worker/workflow redesign could make it viable later |
| Render Free with current SQLite/files | Sleeps on idle and loses local files on restart/spin-down. Avoid for the current live app; external durable persistence requires changes |
| Cloudflare Quick Tunnel | Changing hostname, no uptime guarantee, no SSE support; does not implement public app authorization. Development previews only |

References: [Vercel function limits](https://vercel.com/docs/functions/limitations), [Render Free persistence and sleep](https://render.com/docs/free), [Quick Tunnel limits](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/). Supabase has a [Free plan](https://supabase.com/docs/guides/platform/billing-on-supabase), but choosing it does not migrate this backend or supply its worker.

## Hosting work remaining

1. Production hostname, HTTPS origin, private Supabase bucket and all 15 server settings are configured. Reuse them on redeploy; see the [runbook](../operations/VERCEL_SUPABASE.md).
2. Actual hosted authentication and event delivery passed. Keep the access code private and retain hosted local-entry restrictions.
3. Choose a dedicated judge instance or isolate user state correctly. A public director session shares chats, controls and API budget. A general multi-user service needs more than a login screen.
4. Actual Postgres, private Storage, file mirroring and exclusive worker ownership passed. Local history remains available with paid inference disabled.
5. Preserve the current cloud ledger across releases. The user expressly authorized a fresh $24 cloud cap rather than importing local charges; that one-time action must never repeat on deployment. Additional-payment authority remains $0.
6. Follow the replacement-deployment checks in [production acceptance](../operations/PRODUCTION_ACCEPTANCE.md). Continue monitoring free quotas and retain honest unknown-charge behavior.

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
