# Render Free + Supabase Free versus Vercel Hobby + Supabase Free

Checked October 24, 2026. Neither route has been deployed or validated on an actual user cloud account. The remote database/object-storage conversion is still outstanding.

| Criterion for ZeroWall | Render Free + Supabase | Vercel Hobby + Supabase |
| --- | --- | --- |
| Execution layout | Existing React/FastAPI service plus executor in one web-service process | Frontend and Python API service, with the continuous executor in one separate Daemon |
| Change beyond remote persistence | Smaller: retain the current combined process | Larger: separate API/worker entrypoints and coordinate through the remote queue |
| Idle behavior | Web service sleeps after 15 idle minutes; documented wake-up is about one minute | The documented daemon model keeps configured instances running within quotas; service/function requests can still have cold-start latency |
| Worker resources | 0.1 CPU and 512 MB RAM for the whole free web service | Hobby Daemon: 1 vCPU, choice of 1 or 2 GiB RAM |
| Main compute allowance | 750 free instance-hours per workspace/month, plus bandwidth/build limits and a service-initiated traffic threshold | Daemons: 5 Active CPU-hours/month. Waiting is excluded, but polling, parsing, encryption and token counting use CPU. API/function quotas also apply separately |
| Limit exhaustion | Service/build suspension without a payment method; high outbound service traffic may also trigger suspension | Hobby daemon stops until next month when its active-CPU allowance is exhausted; no daemon overage billing on Hobby |
| Platform status relevant to council | Conventional container/web-service deployment | Services and Daemons are beta; Daemons are production-only and do not accept HTTP traffic |
| Local durable disk | Unavailable on Free | Unavailable for Daemons |
| Persisted history/source data | Supabase Postgres and private Storage | Same Supabase Postgres and private Storage |
| Existing model/search APIs | Token Factory and Tavily | Same APIs and same credit cap |

Sources: [Render Free limits](https://render.com/docs/free), [Render compute resources](https://render.com/docs/compute-plans), [Vercel Daemons and execution model](https://vercel.com/docs/daemons), [daemon limits/quotas](https://vercel.com/docs/daemons/limits), [Services](https://vercel.com/docs/services), [Hobby plan](https://vercel.com/docs/plans/hobby). A daemon's 5-hour active-CPU allowance is not five hours of elapsed model generation or service uptime. The ordinary API/function compute allowance is separate.

## Common work required by both routes

Move SQLite records, job state and the financial ledger to Postgres; move source bytes, original provider artifacts and exports to private Storage. Retain hashes and answer-first persistence. Coordinate worker ownership across deployment replacement. Preserve already-spent credit and unknown reservations; do not create an independent fresh $24 allowance in cloud.

Supabase's Free database/storage limits and inactivity pausing affect both options equally. A faster frontend does not resolve a paused database. [Free allowances](https://supabase.com/docs/guides/platform/billing-on-supabase), [pausing](https://supabase.com/docs/guides/platform/free-project-pausing)

## Local capacity probe

The existing tested Linux image was started under a 512 MiB memory cap with no API keys or inference. It constructed the app, opened its local test database and loaded/verified the three configured tokenizers. Reported peak RSS was **248.4 MiB**. The probe used a temporary container data directory; the developer database was untouched.

This establishes startup fit for that image under the cap. It does not simulate Render's 0.1 CPU, network latency, Postgres adapter overhead, many users or a large 262K-context council. Full workload capacity remains an acceptance gate.

## Recommendation for this project

For the smallest migration before a demo, Render is simpler. For the user's preference for a more responsive interface and avoiding Render's one-minute wake-up, Vercel is the stronger candidate **if its beta features are available to the account and measured CPU usage fits Hobby**. It provides more worker headroom, with additional deployment/separation work.

Vercel Hobby is for personal/non-commercial use; later commercial operation requires checking the appropriate plan. No paid upgrade is authorized. Neither free option guarantees uninterrupted availability. Choose one hosting stack rather than combining Render and Vercel unnecessarily.

Implementation checklist: [free hosting conversion](../../plans/13_FREE_HOSTING.md). Host-specific conversion is on hold while the user compares the routes; local mode and current model behavior remain unchanged.
