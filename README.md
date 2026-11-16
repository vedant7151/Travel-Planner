# Travel Planner — Multi-Agent AI Trip Planning

[![CI](https://github.com/vedant7151/Travel-Planner/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/vedant7151/Travel-Planner/actions/workflows/ci.yml)

A full-stack application that turns a trip request (origin, destination, dates, budget, interests) into a structured travel plan. A LangGraph supervisor coordinates specialist agents (destination research, itinerary, accommodation, transport) and an aggregator merges their output into one plan. Progress streams to the browser over an authenticated WebSocket.

The engineering focus is on what usually gets skipped in LLM demos: **authentication, database-enforced authorization, validated model output, honest failure reporting, rate-limit handling, and automated tests.**

## Highlights

| Area | What is implemented |
|---|---|
| **Auth** | Supabase Auth. The FastAPI backend verifies the JWT signature (JWKS or shared secret) and expiry on every REST route; the WebSocket authenticates before the connection is accepted. |
| **Authorization** | Postgres Row-Level Security on `trips`. Each request runs in its own transaction as the `authenticated` role with the caller's JWT claims set, so `auth.uid()` is enforced by the database, not only by application `WHERE` clauses. Role-based access (`admin`) is carried in a custom access-token claim. |
| **Structured outputs** | Every agent's LLM output is parsed into a Pydantic model, with a bounded repair/retry loop. If parsing still fails, the section is marked unavailable rather than silently filled with nulls. |
| **Honest status** | A trip is `completed`, `partial` (usable plan, some sections degraded) or `failed`, derived from per-section results. The API and UI show degraded sections explicitly. |
| **Resilience** | Exponential backoff with jitter on 429/5xx, pre-flight provider rate gates, and automatic Groq → Gemini fallback when a Gemini key is configured. |
| **Redis (optional)** | Upstash Redis for response caching, provider rate gates and a self-expiring (30 min) distributed run lock. All Redis paths fail open with a logged warning. |
| **Migrations** | Versioned, forward-only SQL in `supabase/migrations/`, applied with the Supabase CLI as an explicit deploy step. |
| **Tests & CI** | 167 backend tests (pytest) and a frontend suite (Vitest), with no real network calls. RLS is tested against a real disposable Postgres. GitHub Actions runs lint, tests and the frontend build. |

## Architecture

```
React (Vite, Tailwind) ──REST + WebSocket──▶ FastAPI ──▶ LangGraph
        │                                       │            supervisor ─▶ destination
        └── Supabase Auth (JWT) ───────────────▶│                       ─▶ itinerary
                                                │                       ─▶ accommodation
                                       Supabase Postgres (RLS)          ─▶ transport
                                       + LangGraph checkpointer         ─▶ aggregator ─▶ plan
                                                │
                                        Upstash Redis (optional)
```

| Layer | Technology |
|---|---|
| Agents | LangGraph + LangChain |
| LLM | Groq (primary), Gemini (optional fallback) |
| Backend | FastAPI (async), asyncpg / psycopg, slowapi |
| Frontend | React 19, Vite, Tailwind CSS 4, Framer Motion |
| Database / Auth | Supabase Postgres and Supabase Auth |
| Data sources (no API keys) | DuckDuckGo search, Open-Meteo, Nominatim (OSM), OSRM |
| Observability | Structured JSON logs, optional LangSmith |

### API

All routes are under `/api/v1/trips` and require a valid Supabase JWT.

| Route | Purpose |
|---|---|
| `POST /plan` | Create a trip and start planning (rate-limited, 5 requests/min per IP) |
| `POST /{id}/run` | Re-run planning for an existing trip |
| `GET /history`, `GET /{id}`, `GET /{id}/status` | List, fetch and poll the caller's trips |
| `GET /{id}/events`, `GET /{id}/errors` | Per-trip agent event and error log |
| `PUT /{id}/preferences` | Update trip preferences |
| `GET /admin/all` | Admin role only |
| `WS /ws/plan/{id}` | Live agent progress (authenticated before accept) |

## Quick start

Requirements: Python 3.11+ (CI uses 3.12), Node 20+, a Supabase project and a Groq API key.

```bash
# 1. Configure
cp .env.example backend/.env          # fill in GROQ_API_KEY, DATABASE_URL, SYSTEM_DATABASE_URL, SUPABASE_*
cp frontend/.env.example frontend/.env  # VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY

# 2. Apply the schema (see "Database migrations")
npx supabase db push --db-url "$SYSTEM_DATABASE_URL"

# 3. Backend  → http://localhost:8000/docs
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py

# 4. Frontend → http://localhost:5173 (proxies /api and /ws to the backend)
cd frontend
npm install
npm run dev
```

In the Supabase dashboard, enable `public.custom_access_token_hook` under **Authentication → Hooks → Custom Access Token** so that admin users receive the `user_role=admin` claim.

`backend/.env.example` and the root `.env.example` list every supported variable. Only the Groq key and the database / Supabase settings are required.

## Security model

- **Two database connections, on purpose.** `DATABASE_URL` serves request-scoped queries: each request sets `request.jwt.claims` and runs as the `authenticated` role, so RLS applies. `SYSTEM_DATABASE_URL` is privileged and used only for migrations, the LangGraph checkpointer, and the internal `trip_events` / `trip_errors` tables. Those internal tables intentionally have no RLS and are never exposed to clients.
- **The frontend only ever holds the Supabase publishable/anon key.** No service-role key is reachable from the browser.
- **Verification, not decoding.** Tokens are checked for signature and expiry on every request.
- **Tested, not assumed.** `tests/db/test_rls.py` applies the real migration SQL to a throwaway Postgres, creates two users and asserts that one cannot read, list or update the other's trips, including with an attacker-chosen `user_id`.

## Database migrations

Schema changes are versioned SQL files in `supabase/migrations/`, applied with the Supabase CLI (`npx supabase ...`, no global install).

```bash
npx supabase migration new add_some_column                # create
npx supabase db push --db-url "$SYSTEM_DATABASE_URL"      # apply to the hosted project
npx supabase start                                        # or: fresh local DB (needs Docker)
```

Migrations are forward-only: to undo a change, write a new migration that reverses it. The `*_add_trips_throwaway_column` / `*_drop_trips_throwaway_column` pair demonstrates that round trip.

Alembic was considered and not used: the backend uses raw `asyncpg` / `psycopg` with no SQLAlchemy models, so Alembic's autogeneration would add nothing, and the schema relies on Supabase-specific primitives (`auth.users` triggers, `auth.uid()` in policies) that the Supabase CLI handles natively.

## Rate limiting and provider backoff

`POST /plan` is limited to 5 requests/minute per client IP using slowapi. Outbound provider calls pass through gates that reserve 20% headroom below the configured limit:

| Provider | Configured limit | Effective gate (80%) |
|---|---:|---:|
| Groq | `GROQ_TPM_LIMIT=10000` tokens/min | 8000 tokens/min (estimated) |
| Gemini | `GEMINI_RPM_LIMIT=10` requests/min | 8 requests/min |
| Nominatim | 1 request/s | 1 request/s |
| OSRM, Open-Meteo, Openverse, FX | 30 requests/min | 30 requests/min |

The default limits are conservative placeholders; set them to match your own provider plan. If both LLM providers are unavailable, the agent reports an error and the trip is marked `partial` or `failed`. It never returns an empty result as if it had succeeded.

## Testing

```bash
cd backend && pip install -r requirements.txt
python -m pytest --cov=app --cov-report=term-missing   # 167 tests, ~58% statement coverage

cd frontend && npm install && npm test
```

- All external services (Groq, Gemini, Nominatim, Open-Meteo, OSRM, DuckDuckGo, Openverse, FX) are mocked: LLM calls at `app.core.llm.invoke_llm`, HTTP via `respx`. No credentials, Docker or network access are needed.
- A `block_network` fixture fails any test that opens a non-loopback socket.
- RLS tests run against a disposable Postgres (`pgserver`) with the real migration files and a minimal stub of Supabase's `auth` schema.
- CI (`.github/workflows/ci.yml`) runs ruff, pytest with coverage, the frontend build and Vitest, and needs no secrets.

## Known limitations

Stated up front so they are not a surprise:

- **Content sourcing is the weakest part.** Accommodation and transport results come from DuckDuckGo text snippets, and prices are extracted from those snippets, so they are indicative and not verified. There is no booking or live-fare API. Transport routing uses OSRM driving routes only.
- **Itineraries are not POI-driven.** Activities are generated by the LLM from destination research. Interests influence the prompt but are not backed by a points-of-interest data source.
- **Budget handling is display-level.** Budgets are converted between currencies for display; the planner does not optimise or enforce a total.
- **Weather is fetched but not yet rendered** in the UI.
- **Rate limiting is per-process unless `REDIS_URL` is set.** Without it, slowapi falls back to in-memory storage, and Nominatim's gate is off unless Upstash is configured. Behind a reverse proxy, forwarded client IPs must be configured correctly for per-IP limits to be meaningful.
- **Test coverage stops short of the HTTP layer.** Core logic, agents, tools and RLS are well covered; `trips.py`, `ws.py`, `graph.py` and `main.py` have no integration tests yet, so the route-level auth wiring is verified by reading and by the RLS tests, not by an end-to-end HTTP test.
- **Background planning and RLS context.** Planning runs as a background task, and its final status writes are not yet pinned to the requesting user's RLS context. They only ever complete an already-authorised trip and never act on caller-supplied identity, but making that explicit is open work.
- **Type checking is not a CI gate.** `mypy` reports pre-existing errors in the loosely-typed agent state, so CI runs ruff and tests only.
