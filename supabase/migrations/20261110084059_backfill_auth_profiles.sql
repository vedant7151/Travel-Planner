-- Backfill profiles for any auth.users rows created before the
-- on_auth_user_created trigger (migration auth_rls) existed.
INSERT INTO public.profiles (id)
SELECT id FROM auth.users
ON CONFLICT (id) DO NOTHING;
