import json
from contextlib import asynccontextmanager
from typing import Any, Optional

import asyncpg

from app.core.auth import get_request_user
from app.core.config import (
    DATABASE_URL,
    asyncpg_connect_kwargs,
    system_database_url,
)
from app.core.logging import logger

_system_pool: Optional[asyncpg.Pool] = None
_user_pool: Optional[asyncpg.Pool] = None


async def _create_pool(url: str) -> asyncpg.Pool:
    import ssl

    ssl_ctx = ssl.create_default_context()
    # Supabase's pooler uses sslmode=require semantics. Keep transport
    # encryption, but do not require a locally trusted CA chain.
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    return await asyncpg.create_pool(
        **asyncpg_connect_kwargs(url),
        min_size=1,
        max_size=5,
        ssl=ssl_ctx,
        # Supabase's transaction-mode pooler does not support asyncpg's
        # prepared-statement cache.
        statement_cache_size=0,
        command_timeout=60,
    )


async def get_system_pool() -> asyncpg.Pool:
    global _system_pool
    if _system_pool is None:
        _system_pool = await _create_pool(system_database_url())
    return _system_pool


async def get_user_pool() -> asyncpg.Pool:
    global _user_pool
    if _user_pool is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured")
        _user_pool = await _create_pool(DATABASE_URL)
    return _user_pool


async def get_pool() -> asyncpg.Pool:
    """Compatibility accessor for system-internal database work."""
    return await get_system_pool()


@asynccontextmanager
async def user_connection():
    current_user = get_request_user()
    if current_user is None:
        raise RuntimeError("Authenticated request context is required for user queries")
    pool = await get_user_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL ROLE authenticated")
            await conn.execute(
                "SELECT set_config('request.jwt.claims', $1, true)",
                json.dumps(current_user.claims),
            )
            yield conn


@asynccontextmanager
async def system_connection():
    pool = await get_system_pool()
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def scoped_connection():
    if get_request_user() is None:
        async with system_connection() as conn:
            yield conn
    else:
        async with user_connection() as conn:
            yield conn


async def close_pool() -> None:
    global _system_pool, _user_pool
    if _system_pool is not None:
        await _system_pool.close()
        _system_pool = None
    if _user_pool is not None:
        await _user_pool.close()
        _user_pool = None


def _parse_json(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        return json.loads(val)
    return val


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    data = dict(row)
    data["request"] = _parse_json(data.get("request"))
    data["final_plan"] = _parse_json(data.get("final_plan"))
    for key in ("created_at", "updated_at"):
        val = data.get(key)
        if val is not None:
            data[key] = val.isoformat()
    return data


async def create_trip(trip_id: str, user_id: str, request: dict[str, Any]) -> dict[str, Any]:
    try:
        async with user_connection() as conn:
            await conn.execute(
                """
                INSERT INTO trips (id, user_id, status, request)
                VALUES ($1, $2, 'queued', $3::jsonb)
                """,
                trip_id,
                user_id,
                json.dumps(request),
            )
    except Exception:
        logger.exception("failed to create trip %s", trip_id)
        raise
    row = await get_trip(trip_id)
    if row is None:
        raise RuntimeError("Trip insert succeeded but row could not be loaded")
    return row


async def get_trip(trip_id: str) -> Optional[dict[str, Any]]:
    async with scoped_connection() as conn:
        row = await conn.fetchrow("SELECT * FROM trips WHERE id = $1", trip_id)
        return _row_to_dict(row) if row else None


async def list_trips(user_id: str) -> list[dict[str, Any]]:
    async with user_connection() as conn:
        rows = await conn.fetch(
            "SELECT * FROM trips WHERE user_id = $1 ORDER BY created_at DESC",
            user_id,
        )
        return [_row_to_dict(r) for r in rows]


async def update_trip_status(
    trip_id: str, status: str, error: Optional[str] = None
) -> None:
    async with scoped_connection() as conn:
        await conn.execute(
            """
            UPDATE trips
            SET status = $1, error = $2, updated_at = NOW()
            WHERE id = $3
            """,
            status,
            error,
            trip_id,
        )


async def update_trip_request(
    trip_id: str, request: dict[str, Any]
) -> Optional[dict[str, Any]]:
    existing = await get_trip(trip_id)
    if not existing:
        return None
    async with user_connection() as conn:
        await conn.execute(
            """
            UPDATE trips
            SET request = $1::jsonb, updated_at = NOW()
            WHERE id = $2
            """,
            json.dumps(request),
            trip_id,
        )
    return await get_trip(trip_id)


async def list_all_trips() -> list[dict[str, Any]]:
    async with user_connection() as conn:
        rows = await conn.fetch("SELECT * FROM trips ORDER BY created_at DESC")
    return [_row_to_dict(r) for r in rows]


async def save_final_plan(
    trip_id: str, final_plan: dict[str, Any], status: str = "completed"
) -> None:
    """Persist the final plan with an explicit status.

    status should be one of "completed" (every section succeeded), "partial"
    (a usable plan exists but one or more sections degraded), or "failed" (no
    usable plan). Callers compute this from degraded-section markers rather
    than assuming success just because a final_plan dict exists.
    """
    async with scoped_connection() as conn:
        await conn.execute(
            """
            UPDATE trips
            SET final_plan = $1::jsonb, status = $2, error = NULL, updated_at = NOW()
            WHERE id = $3
            """,
            json.dumps(final_plan),
            status,
            trip_id,
        )
