# Deploying Smart Expense Tracker

```
iPhone ──► <app>.vercel.app ──(/api/* forwarded)──► <api>.onrender.com ──► Supabase Postgres
            React files                              FastAPI (Docker)        database
```

The browser only ever talks to Vercel. Vercel forwards `/api/...` to Render, so the
login cookie is filed under the Vercel site and iPhone Safari sends it (no
third-party cookie). Secrets live in each service's dashboard, never in git.

---

## Step 7.1 — Database (Supabase) and API (Render)

### A. Supabase: the database

1. Sign up at supabase.com → **New project**.
   - Name: `smart-expense-tracker`
   - Database password: press **Generate**, save it in your password manager.
   - Region: **London (eu-west-2)** — close to you and to Render's EU region.
2. When it's ready: **Connect** (top bar) → **Connection string** → pick
   **Session pooler** (not "Direct": that one is IPv6-only and Render can't reach it).
3. Copy the URI. It looks like
   `postgresql://postgres.<id>:[YOUR-PASSWORD]@aws-0-eu-west-2.pooler.supabase.com:5432/postgres`
4. Make two changes to it (in your password manager, not in a file in this repo):
   - put your database password in place of `[YOUR-PASSWORD]`
   - change the start `postgresql://` to `postgresql+psycopg://` (tells SQLAlchemy
     which driver to use, the same as your local `.env`)

You don't create any tables: the API runs `alembic upgrade head` every time it starts.

### B. Render: the API

1. Sign up at render.com with your GitHub account → **New** → **Web Service** →
   pick the `SmartExpenseTracker` repo.
2. Settings:
   - Name: `smart-expense-api` (becomes `smart-expense-api.onrender.com`)
   - Region: **Frankfurt (EU Central)**
   - Branch: `main`
   - Root Directory: `backend`
   - Language / Runtime: **Docker** (it finds `backend/Dockerfile`)
   - Instance type: **Free**
3. **Environment Variables** (Add from .env is fine, but paste values by hand):

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Supabase URL from A.4 |
   | `OPENAI_API_KEY` | your OpenAI key |
   | `JWT_SECRET_KEY` | a **new** one: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `COOKIE_SECURE` | `true` |
   | `COOKIE_PATH` | `/api/auth` |

   `CORS_ORIGINS` comes in step 7.2, once the Vercel address exists.
4. **Advanced** → Health Check Path: `/health`.
5. **Create Web Service**. Watch the log: the Docker build, then
   `alembic.runtime.migration ... Running upgrade` lines, then `Application startup complete`.

### C. Check it

- `https://smart-expense-api.onrender.com/health` → `{"status":"ok"}`
- `https://smart-expense-api.onrender.com/docs` → the API docs page
- Supabase → **Table Editor** → the tables (`expenses`, `users`, ...) now exist.

Free-plan note: the API sleeps after 15 minutes without requests; the next request
wakes it in ~30–50 s.

---

## Later steps

- **7.2** Vercel (frontend) + the `/api` proxy (`vercel.json`), then `CORS_ORIGINS`
- **7.3** Your account in production (an invite code for the new database)
- **7.4** Rate limits, the OpenAI spending cap, usage logging
