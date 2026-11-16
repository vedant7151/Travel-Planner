-- These tables are written and read only by the privileged system connection.
ALTER TABLE IF EXISTS public.trip_events DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.trip_errors DISABLE ROW LEVEL SECURITY;
