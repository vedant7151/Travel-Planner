"""Fixtures for RLS/auth-boundary tests.

Spins up a disposable local Postgres via pgserver (no Docker, no real
Supabase project, no network) and applies the real supabase/migrations/*.sql
files against it -- the same migrations the hosted Supabase project runs.
Supabase's own `auth` schema (auth.users, auth.uid(), auth.jwt()) is stubbed
with the minimal pieces our policies depend on: auth.uid()/auth.jwt() read
from the `request.jwt.claims` GUC exactly like the real Supabase Postgres
does, which is also exactly what app/db/postgres.py's user_connection() sets
via `SET LOCAL ROLE` + `set_config('request.jwt.claims', ...)`. This lets the
tests exercise the real RLS policies, not a Python re-implementation of them.
"""
import glob
import json
import tempfile
import uuid
from pathlib import Path

import psycopg
import pytest

try:
    import pgserver
except ImportError:  # pragma: no cover
    pgserver = None

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MIGRATIONS_DIR = _REPO_ROOT / "supabase" / "migrations"
_PG_DATA_DIR = Path(tempfile.gettempdir()) / "travel_planner_pg_rls_test"


def _bootstrap_schema(dsn: str) -> None:
    conn = psycopg.connect(dsn, autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS auth;")
        cur.execute("CREATE TABLE IF NOT EXISTS auth.users (id UUID PRIMARY KEY);")
        # Faithful stand-ins: the real Supabase auth.uid()/auth.jwt() read
        # the request.jwt.claims GUC set by PostgREST/the app's connection
        # for each request -- exactly what user_connection() does.
        cur.execute(
            """
            CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID
            LANGUAGE sql STABLE AS $$
                SELECT (NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')::uuid
            $$;
            """
        )
        cur.execute(
            """
            CREATE OR REPLACE FUNCTION auth.jwt() RETURNS JSONB
            LANGUAGE sql STABLE AS $$
                SELECT COALESCE(NULLIF(current_setting('request.jwt.claims', true), '')::jsonb, '{}'::jsonb)
            $$;
            """
        )
        for role in ("supabase_auth_admin", "authenticated", "anon"):
            cur.execute(
                f"DO $$ BEGIN "
                f"CREATE ROLE {role}; "
                f"EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
            )

        for f in sorted(glob.glob(str(_MIGRATIONS_DIR / "*.sql"))):
            cur.execute(Path(f).read_text(encoding="utf-8"))
    finally:
        conn.close()


@pytest.fixture(scope="session")
def pg_dsn():
    if pgserver is None:
        pytest.skip("pgserver is not installed")
    if not _MIGRATIONS_DIR.exists():
        pytest.skip(f"no migrations found at {_MIGRATIONS_DIR}")

    server = pgserver.get_server(str(_PG_DATA_DIR))
    try:
        dsn = server.get_uri()
        _bootstrap_schema(dsn)
        yield dsn
    finally:
        server.cleanup()


@pytest.fixture()
def db(pg_dsn):
    """A superuser (table-owner) connection, truncated clean before each test."""
    conn = psycopg.connect(pg_dsn, autocommit=True)
    conn.execute("TRUNCATE TABLE public.trips, auth.users CASCADE;")
    try:
        yield conn
    finally:
        conn.close()


def make_user(db, user_id: str | None = None) -> str:
    user_id = user_id or str(uuid.uuid4())
    db.execute("INSERT INTO auth.users (id) VALUES (%s) ON CONFLICT DO NOTHING;", (user_id,))
    return user_id


@pytest.fixture()
def user_a(db):
    return make_user(db)


@pytest.fixture()
def user_b(db):
    return make_user(db)


class AuthenticatedConnection:
    """Mirrors app/db/postgres.py's user_connection(): SET LOCAL ROLE
    authenticated + set_config('request.jwt.claims', ...) inside a
    transaction, so auth.uid()/auth.jwt() resolve to the given claims and
    RLS policies apply exactly as they do for a real request.
    """

    def __init__(self, dsn: str, claims: dict):
        self._dsn = dsn
        self._claims = claims
        self._conn: psycopg.Connection | None = None

    def __enter__(self):
        self._conn = psycopg.connect(self._dsn, autocommit=False)
        cur = self._conn.cursor()
        cur.execute("SET LOCAL ROLE authenticated;")
        cur.execute(
            "SELECT set_config('request.jwt.claims', %s, true);",
            (json.dumps(self._claims),),
        )
        return self._conn

    def __exit__(self, *exc):
        if self._conn is not None:
            self._conn.rollback()
            self._conn.close()


@pytest.fixture()
def as_user(pg_dsn):
    """as_user(user_id, role="user") -> context manager yielding a psycopg
    connection acting as that authenticated user."""

    def _factory(user_id: str, role: str = "user"):
        return AuthenticatedConnection(pg_dsn, {"sub": user_id, "user_role": role})

    return _factory
