-- LangGraph owns these tables; access is always through the privileged
-- system connection, not an end-user JWT. The tables themselves are created
-- lazily by AsyncPostgresSaver.setup() on app startup, not by this migration
-- -- this only guarantees RLS stays off once they exist.
ALTER TABLE IF EXISTS public.checkpoints DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.checkpoint_blobs DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.checkpoint_writes DISABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.checkpoint_migrations DISABLE ROW LEVEL SECURITY;
