# Set up CouncilAI on Vercel and Supabase

Repository: https://github.com/AlphaSudo/CouncilAI. Use Vercel Hobby and Supabase Free. Source publication does not deploy the app or authorize model charges.

## 1. Supabase

1. Sign in at https://supabase.com/dashboard. Create a Free organization if necessary, then **New project**.
2. Project name: `councilai`. Generate and privately save a database password. Choose **US East / North Virginia** if available, matching the supplied Vercel `iad1` worker region. If you choose another region, change the worker region in `vercel.json` before deployment.
3. Open **Storage**, create bucket **`zerowall-private`**, and leave **Public bucket off**. Leave MIME restrictions unset; the server stores several file types as `application/octet-stream`. No anonymous upload/read policy is needed.
4. Open **Connect**, select **Session pooler**, and copy the PostgreSQL URI on **port 5432**. Replace the password placeholder with the URL-encoded database password and append `?sslmode=require` (or `&sslmode=require` when a query already exists). Do not select the transaction pooler on 6543: the queue uses session ownership and notifications. [Supabase connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres)
5. Copy the **Project URL** from Connect, and create/copy a server secret key under **Settings → API Keys**. Prefer the new `sb_secret_…` key. The app supports this through the `apikey` header; legacy service-role JWTs are also supported. Keep the server key private. [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys)

Fill these in the ignored local `.env.cloud` file:

| Variable | Value |
| --- | --- |
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| `SUPABASE_SECRET_KEY` | Your server secret key |
| `ZEROWALL_DATABASE_URL` | Complete Session pooler URI, with encoded password and TLS |
| `ZEROWALL_PUBLIC_ORIGIN` | The final Vercel production HTTPS origin, once assigned |

`python scripts/prepare_cloud_env.py` creates this private file without overwriting an existing one. It generates a new director access code and reuses the existing local Nebius/Tavily keys. The file is ignored by Git and is not automatically loaded by the app. Leave `.env.local` unchanged. The local cloud-admin file uses a Windows temporary cache path; the Vercel value must be `/tmp/zerowall`.

## 2. Vercel

1. Sign in at https://vercel.com using GitHub, using a **Hobby** personal account.
2. Choose **Add New → Project**, grant access to **AlphaSudo/CouncilAI**, and import it.
3. Select production branch **`main`**, root directory **the repository root (`.`)**, and framework preset **Other** if prompted. Leave build/install/output overrides unset. The root `vercel.json` and Dockerfile define the build, web Service and worker Daemon. Do not set the root to `apps/web` or add a second deployment project for the frontend.
4. Add the following variables for **Production only**, not Preview or Development:

| Variable | Value |
| --- | --- |
| `ZEROWALL_MODE` | `hosted` |
| `ZEROWALL_STORAGE` | `supabase` |
| `ZEROWALL_ROLE` | `web` |
| `ZEROWALL_DATA_DIR` | `/tmp/zerowall` |
| `ZEROWALL_PUBLIC_ORIGIN` | The assigned production `https://…vercel.app` origin, no path |
| `ZEROWALL_DIRECTOR_TOKEN` | Generated access code from the private `.env.cloud` file |
| `ZEROWALL_DATABASE_URL` | Supabase Session pooler URI from step 1 |
| `SUPABASE_URL` | Supabase Project URL |
| `SUPABASE_SECRET_KEY` | Supabase server secret key |
| `ZEROWALL_STORAGE_BUCKET` | `zerowall-private` |
| `NEBIUS_API_KEY` | Existing Token Factory key |
| `TAVILY_API_KEY` | Existing Tavily key |
| `ZEROWALL_OPENROUTER_ENABLED` | `false` |
| `ZEROWALL_DIRECT_FREE_CONFIRMED` | `false` |
| `ZEROWALL_SEARCH_MONTHLY_LIMIT` | `900` |

Use Vercel's sensitive/server environment settings for credentials. No `VITE_` prefix: those variables must not enter the browser bundle. Vercel's dashboard uses your GitHub login/repository connection; manual deployment needs no separate Vercel API token. Supabase Auth and a publishable/anon frontend key are not used by this app.

5. Confirm the production hostname under **Settings → Domains**. If Vercel assigns a different hostname during project creation, update `ZEROWALL_PUBLIC_ORIGIN` and redeploy before testing the URL. Use the actual assigned name, not a guessed name or deployment-specific preview URL.
6. Deploy and confirm there is one **web Service** and one **council-worker Daemon**. Both use the same image; the commands set their respective roles. Confirm Services/Daemons are available on this Hobby project; no paid upgrade is authorized. [Services](https://vercel.com/docs/services), [Daemons](https://vercel.com/docs/daemons)

Hobby's Daemon allowance is finite: currently five active CPU hours per month; the worker stops when exhausted. Waiting does not count as active CPU. Check free-plan usage during testing and judging. [Daemon limits](https://vercel.com/docs/daemons/limits)

## 3. Before the first live model request

The cloud app stays locked for paid inference until the existing local spending ledger is imported. **Do not initialize a fresh $24 allowance.** Keep the local server running normally until the explicit cutover is scheduled; cutover requires it to be stopped and its prior charges retained. The default migration excludes private conversations/documents.

After account setup, confirm that the four Supabase/origin fields are saved locally, and provide only the public Vercel URL in chat. The next steps are private connectivity/bucket checks, a ledger inventory/backup, explicit cutover, then an offline demo and a small live test within the existing cap. The detailed commands and recovery rules are in [VERCEL_SUPABASE.md](VERCEL_SUPABASE.md).
