"""RLS/auth boundary tests (Phase 3): two simulated Supabase users, confirmed
against the real public.trips RLS policies from supabase/migrations/, not a
Python re-implementation of them. See tests/db/conftest.py for how the
Postgres instance and auth stubs are set up (local, no network, no Docker).
"""
import json

import psycopg
import pytest


def _insert_trip(db, trip_id: str, user_id: str) -> None:
    db.execute(
        "INSERT INTO public.trips (id, user_id, status, request) VALUES (%s, %s, 'queued', %s::jsonb);",
        (trip_id, user_id, json.dumps({"destination": "Paris"})),
    )


class TestTripsRLS:
    def test_owner_can_select_own_trip(self, db, user_a, as_user):
        _insert_trip(db, "trip-a", user_a)
        with as_user(user_a) as conn:
            rows = conn.execute("SELECT id FROM public.trips WHERE id = 'trip-a';").fetchall()
        assert rows == [("trip-a",)]

    def test_other_user_cannot_select_someone_elses_trip(self, db, user_a, user_b, as_user):
        _insert_trip(db, "trip-a", user_a)
        with as_user(user_b) as conn:
            rows = conn.execute("SELECT id FROM public.trips WHERE id = 'trip-a';").fetchall()
        assert rows == []

    def test_other_user_cannot_select_via_unfiltered_query(self, db, user_a, user_b, as_user):
        """Even a `SELECT * FROM trips` with no WHERE clause must not leak
        another user's row -- RLS filters rows, it doesn't just gate a
        specific query shape."""
        _insert_trip(db, "trip-a", user_a)
        _insert_trip(db, "trip-b", user_b)
        with as_user(user_b) as conn:
            rows = conn.execute("SELECT id FROM public.trips;").fetchall()
        assert rows == [("trip-b",)]

    def test_admin_can_select_other_users_trip(self, db, user_a, user_b, as_user):
        _insert_trip(db, "trip-a", user_a)
        with as_user(user_b, role="admin") as conn:
            rows = conn.execute("SELECT id FROM public.trips WHERE id = 'trip-a';").fetchall()
        assert rows == [("trip-a",)]

    def test_owner_can_insert_own_trip(self, db, user_a, as_user):
        with as_user(user_a) as conn:
            conn.execute(
                "INSERT INTO public.trips (id, user_id, status, request) "
                "VALUES ('trip-new', %s, 'queued', '{}'::jsonb);",
                (user_a,),
            )
            rows = conn.execute("SELECT id FROM public.trips WHERE id = 'trip-new';").fetchall()
        assert rows == [("trip-new",)]

    def test_cannot_insert_trip_for_another_user(self, db, user_a, user_b, as_user):
        """WITH CHECK (user_id = auth.uid()) must reject an insert where the
        authenticated user tries to create a trip owned by someone else."""
        with as_user(user_b) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    "INSERT INTO public.trips (id, user_id, status, request) "
                    "VALUES ('trip-spoofed', %s, 'queued', '{}'::jsonb);",
                    (user_a,),
                )

    def test_owner_can_update_own_trip(self, db, user_a, as_user):
        _insert_trip(db, "trip-a", user_a)
        with as_user(user_a) as conn:
            conn.execute("UPDATE public.trips SET status = 'completed' WHERE id = 'trip-a';")
            rows = conn.execute("SELECT status FROM public.trips WHERE id = 'trip-a';").fetchall()
        assert rows == [("completed",)]

    def test_other_user_update_affects_zero_rows(self, db, user_a, user_b, as_user):
        """RLS on UPDATE's USING clause filters which rows are visible to be
        updated at all -- the statement succeeds but touches nothing."""
        _insert_trip(db, "trip-a", user_a)
        with as_user(user_b) as conn:
            cur = conn.execute("UPDATE public.trips SET status = 'completed' WHERE id = 'trip-a';")
            assert cur.rowcount == 0
        # Confirm, as the real owner, that the row was untouched.
        with as_user(user_a) as conn:
            rows = conn.execute("SELECT status FROM public.trips WHERE id = 'trip-a';").fetchall()
        assert rows == [("queued",)]

    def test_no_delete_grant_means_delete_is_rejected(self, db, user_a, as_user):
        """No DELETE grant exists for `authenticated` on trips at all (by
        design -- trips are append/update only from the API), so even the
        owner's delete is rejected outright, not silently a no-op."""
        _insert_trip(db, "trip-a", user_a)
        with as_user(user_a) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("DELETE FROM public.trips WHERE id = 'trip-a';")

    def test_unauthenticated_role_has_no_access(self, db, user_a, pg_dsn):
        """A connection that never assumes the `authenticated` role (e.g. a
        stray anon session) must not see any trips."""
        _insert_trip(db, "trip-a", user_a)
        conn = psycopg.connect(pg_dsn, autocommit=False)
        try:
            conn.execute("SET LOCAL ROLE anon;")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("SELECT id FROM public.trips;")
        finally:
            conn.rollback()
            conn.close()


class TestProfilesRLS:
    def test_authenticated_role_cannot_read_profiles(self, db, user_a, as_user):
        """profiles access is reserved for supabase_auth_admin (the custom
        access token hook); REVOKE ALL FROM authenticated/anon/public means
        a normal user session gets a permission error, not an empty result."""
        db.execute("INSERT INTO public.profiles (id) VALUES (%s) ON CONFLICT DO NOTHING;", (user_a,))
        with as_user(user_a) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("SELECT id FROM public.profiles;")

    def test_supabase_auth_admin_can_read_profiles(self, db, user_a, pg_dsn):
        db.execute("INSERT INTO public.profiles (id) VALUES (%s) ON CONFLICT DO NOTHING;", (user_a,))
        conn = psycopg.connect(pg_dsn, autocommit=False)
        try:
            conn.execute("SET LOCAL ROLE supabase_auth_admin;")
            rows = conn.execute("SELECT id FROM public.profiles WHERE id = %s;", (user_a,)).fetchall()
            assert [str(r[0]) for r in rows] == [user_a]
        finally:
            conn.rollback()
            conn.close()
