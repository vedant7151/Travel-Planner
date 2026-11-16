-- Core application tables: trips, and the system-internal event/error logs
-- written by the LangGraph agent pipeline.

CREATE TABLE IF NOT EXISTS public.trips (
    id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    request JSONB NOT NULL,
    final_plan JSONB,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.trips ADD COLUMN IF NOT EXISTS error TEXT;
ALTER TABLE public.trips ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

UPDATE public.trips SET updated_at = COALESCE(updated_at, created_at, NOW()) WHERE updated_at IS NULL;

CREATE INDEX IF NOT EXISTS trips_user_id_idx ON public.trips (user_id);
CREATE INDEX IF NOT EXISTS trips_status_idx ON public.trips (status);

CREATE TABLE IF NOT EXISTS public.trip_events (
    id BIGSERIAL PRIMARY KEY,
    trip_id TEXT NOT NULL REFERENCES public.trips(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    agent TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS trip_events_trip_id_created_idx
    ON public.trip_events (trip_id, created_at);

CREATE TABLE IF NOT EXISTS public.trip_errors (
    id BIGSERIAL PRIMARY KEY,
    trip_id TEXT REFERENCES public.trips(id) ON DELETE SET NULL,
    agent TEXT,
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS trip_errors_trip_id_idx ON public.trip_errors (trip_id, created_at);
