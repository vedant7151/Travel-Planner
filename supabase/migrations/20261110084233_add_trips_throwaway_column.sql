-- Throwaway migration demonstrating the forward-only apply/rollback workflow.
-- Paired with the immediately following drop_trips_throwaway_column migration.
ALTER TABLE public.trips ADD COLUMN IF NOT EXISTS _migration_smoke_test TEXT;
