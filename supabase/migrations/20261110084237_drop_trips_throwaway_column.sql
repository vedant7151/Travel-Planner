-- Rolls back the throwaway column added in add_trips_throwaway_column.
-- Migrations are forward-only, so "rollback" here is a new forward migration
-- that undoes the previous one -- there is no separate down-migration file.
ALTER TABLE public.trips DROP COLUMN IF EXISTS _migration_smoke_test;
