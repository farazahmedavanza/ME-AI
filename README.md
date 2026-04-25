# API Health & SLA Monitor (hackathon)

Full-stack ops dashboard: **FastAPI** backend with **SQLite** (default) or **Supabase**, optional **OpenRouter** for LLM text, and **Next.js** UI (Avanza dark layout).

## Quick start (judge path, no cloud)

### 1. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python data_generator.py
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- Health: `GET http://127.0.0.1:8000/api/health` — returns `store: local` / `ai: local` without API keys.
- Token: `POST http://127.0.0.1:8000/api/auth/token` — returns a JWT for the UI.
- First run creates `backend/local_store.db` and **seeds** from `backend/data/api_logs.json`.

To reset: delete `backend/local_store.db` and restart.

### 2. Frontend

```powershell
cd frontend
copy .env.local.example .env.local
npm run dev
```

Open [http://localhost:3000/dashboard](http://localhost:3000/dashboard). The app calls `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`).

## Optional: OpenRouter

Set `OPENROUTER_API_KEY` in `backend` environment. Incident reports and NL-parsed filters will try the model first, then **template** + **rule-based** fallbacks on failure or timeout.

## Optional: Supabase

1. Create a project and run [supabase/schema.sql](supabase/schema.sql) in the SQL editor.
2. Set `SUPABASE_URL`, `SUPABASE_KEY` (service role for server), `SUPABASE_JWT_SECRET` (JWT secret from Project Settings → API), and **unset** `USE_LOCAL_STORE` or set `USE_LOCAL_STORE=0`.
3. Use Supabase Auth on the client and pass the same user’s JWT to the backend. The open `POST /api/auth/token` exists only for local judge demos (disable in real deployments).

## Environment variables

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | Optional. If empty, text is template-based. |
| `USE_LOCAL_STORE` | `1` to force SQLite even if Supabase is set. |
| `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_JWT_SECRET` | Supabase (optional). |
| `JWT_SECRET` | Signs local demo tokens from `/api/auth/token`. |
| `CORS_ORIGINS` | Comma-separated origins, default includes `http://localhost:3000`. |
| `NEXT_PUBLIC_API_URL` | FastAPI base URL for the browser. |
| `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Optional: enable **email/password** on `/login` (use with Supabase Auth). |
| `USE_DEGRADED_MODE` | `1` — same as `USE_LOCAL_STORE` (force SQLite). |
| `STORE_AUTO_FALLBACK` | Default `1`: if Supabase is configured but unreachable at startup, use SQLite. Set `0` to fail hard. |

## Design reference

Place your UI reference image at `assets/reference-dashboard.png` to compare while polishing.

## Project layout

- `backend/` — FastAPI, analytics, `store/` (local + supabase), `narrative.py` / `nl_query.py` fallbacks.
- `frontend/` — Next.js 14, Recharts, Tailwind (`#0B1220` / slate tokens).
- `supabase/schema.sql` — production Postgres schema with RLS.
