# Judging availability: December 1–15, 2026

The production council runs on Vercel Hobby and Supabase Free independently of the developer computer. This configuration reduces idle work and checks the actual application database and worker. It cannot guarantee uninterrupted service or increase a free quota.

## Cloud schedules

| Scheduler | Schedule in UTC | Purpose |
| --- | --- | --- |
| Vercel Cron | Daily, 07:23 | Read application metadata and confirm database/worker health |
| GitHub Actions: Council availability | Daily, 07:23 | Independent health check and failure record |
| GitHub Actions: extra judging checks | Hourly at :23 on November 30 and December 1–15 | More frequent preflight/judging checks |

All checks call the public `GET /api/operations/status` endpoint. They make no model or Tavily requests, need no secrets, and never reserve inference credit. Daily application queries also create activity in Supabase. Its official guidance permits activity through the application/API to prevent low-activity pausing. Vercel's daily cron stays inside the Hobby scheduling restriction; its execution time can vary by up to an hour. GitHub scheduled runs can be delayed. [Supabase pausing](https://supabase.com/docs/guides/platform/free-project-pausing), [Vercel cron limits](https://vercel.com/docs/cron-jobs/usage-and-pricing), [GitHub schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

GitHub scheduled HTTP checks stop after **December 15, 2026, 20:00 UTC** (22:00 Cairo). Manual checks remain available. The Vercel daily check remains useful for the app after judging. GitHub may disable schedules in public repositories after 60 days without repository activity; the October 26 activation is within 60 days of the end of judging. Disable the GitHub workflow after judging if it is no longer needed.

## Worker efficiency

The queue consumer blocks on Postgres notifications instead of repeatedly querying while idle. Job notifications still wake it immediately; delayed jobs retain their actual due time. Idle ownership reconciliation runs at most once per minute. File mirroring uses notifications and adaptive idle backoff up to one minute. Active model requests retain their existing ownership, persistence and financial checks. No model output limit, thinking level, context setting or conversation allowance was changed.

Every five minutes the worker publishes a small heartbeat with process CPU time, memory and deployment commit. Public diagnostics contain no history, credentials or spending amounts. A 30-second cache bounds repeated status queries. `/api/ready` continues to check the web service separately, so saved answers remain viewable during a worker outage.

Vercel Hobby currently includes **five active CPU hours per month for Daemons**; time waiting for I/O is excluded. The application's process-CPU observation is advisory and covers instrumented worker processes only. It is **not Vercel's billing meter** and omits older deployments and other billable resources. Diagnostics flag an idle five-minute window above 0.5% process CPU, or observed monthly CPU above 3.5 hours, for investigation. Check the actual Vercel Usage dashboard before judging and when a warning appears. No paid upgrade or automatic billing change is configured by this work. [Daemon limits](https://vercel.com/docs/daemons/limits)

## Inspect and recover

Run a read-only check from any machine with Python 3.11+:

```text
python scripts/check_hosted_availability.py
```

Open [Council availability runs](https://github.com/AlphaSudo/CouncilAI/actions/workflows/judging-availability.yml) to inspect the latest result or run it manually. Failed runs contain a sanitized health summary. GitHub notifications depend on the account's Actions notification preferences; this workflow does not send email or messages itself. Vercel Project Settings → Cron Jobs shows the daily schedule and invocation logs.

| Failed check | Action |
| --- | --- |
| Database unavailable | Check Supabase project status. If paused, use its dashboard Resume action; a query cannot resume an already paused project. |
| Worker unavailable or stale heartbeat | Check Vercel Daemon status/logs and actual CPU quota. A redeploy can recover a crashed process, but cannot reset an exhausted quota. |
| File mirror deferred | Check private Storage availability and quota. Pending bytes remain in Postgres; restore mirroring before the database fills. |
| CPU warning | Inspect actual Vercel usage and worker logs. Do not change answer lengths or reset the spending ledger to hide resource usage. |
| HTTP/network failure | The checker retries only the safe status GET three times. Inspect provider status if it persists. No model request is retried. |

If a free quota is exhausted, service can remain unavailable until the provider resets it. Keep the submitted demo video and judge access instructions current; no scheduler can promise a free-tier SLA. Token Factory funding/expiry and Tavily's monthly quota remain separate from hosting checks.

## Validation

October 26 implementation validation: **79 targeted local regression tests** and **27 Linux integration tests** against real temporary Postgres at a 1 GiB container limit. Tests cover notification wake-up, delayed retry deadlines, mirror shutdown, sanitized diagnostics and unchanged financial authority. The Storage transport is a test double in that integration suite. Live deployment and workflow execution must be checked after publishing; their authoritative evidence is the production status endpoint and the Actions run history above.
