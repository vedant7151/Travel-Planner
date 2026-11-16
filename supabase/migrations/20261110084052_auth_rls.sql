-- Supabase Auth integration: a profiles table keyed off auth.users, a default
-- role for new signups, a custom access token hook that stamps the role onto
-- issued JWTs, and row-level security on public.trips.

CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.profiles (id)
    VALUES (NEW.id)
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event JSONB)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    claims JSONB;
    user_role TEXT;
BEGIN
    SELECT role
    INTO user_role
    FROM public.profiles
    WHERE id = (event->>'user_id')::UUID;

    claims := event->'claims';
    claims := jsonb_set(
        claims,
        '{user_role}',
        to_jsonb(COALESCE(user_role, 'user'::TEXT))
    );
    RETURN jsonb_set(event, '{claims}', claims);
END;
$$;

GRANT USAGE ON SCHEMA public TO supabase_auth_admin;
GRANT EXECUTE ON FUNCTION public.custom_access_token_hook(JSONB) TO supabase_auth_admin;
REVOKE EXECUTE ON FUNCTION public.custom_access_token_hook(JSONB) FROM authenticated, anon, public;
GRANT ALL ON TABLE public.profiles TO supabase_auth_admin;
REVOKE ALL ON TABLE public.profiles FROM authenticated, anon, public;

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow auth admin to read profiles" ON public.profiles;
CREATE POLICY "Allow auth admin to read profiles"
    ON public.profiles
    AS PERMISSIVE
    FOR SELECT
    TO supabase_auth_admin
    USING (TRUE);

ALTER TABLE public.trips ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE ON public.trips TO authenticated;

DROP POLICY IF EXISTS "Users can select their own trips" ON public.trips;
CREATE POLICY "Users can select their own trips"
    ON public.trips
    FOR SELECT
    TO authenticated
    USING (
        user_id = (SELECT auth.uid())
        OR (SELECT auth.jwt() ->> 'user_role') = 'admin'
    );

DROP POLICY IF EXISTS "Users can insert their own trips" ON public.trips;
CREATE POLICY "Users can insert their own trips"
    ON public.trips
    FOR INSERT
    TO authenticated
    WITH CHECK (user_id = (SELECT auth.uid()));

DROP POLICY IF EXISTS "Users can update their own trips" ON public.trips;
CREATE POLICY "Users can update their own trips"
    ON public.trips
    FOR UPDATE
    TO authenticated
    USING (user_id = (SELECT auth.uid()))
    WITH CHECK (user_id = (SELECT auth.uid()));

COMMENT ON TABLE public.trip_events IS
    'System-internal LangGraph events. Accessed by the privileged system database pool; no RLS is applied.';
COMMENT ON TABLE public.trip_errors IS
    'System-internal LangGraph errors. Accessed by the privileged system database pool; no RLS is applied.';
