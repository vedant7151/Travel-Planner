import json
from typing import Any, Optional

from app.core.logging import logger
from app.core.serialize import jsonable
from app.db.postgres import get_system_pool


async def log_event(
    trip_id: Optional[str],
    event_type: str,
    *,
    agent: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    if not trip_id:
        return
    body = jsonable(payload or {})
    try:
        pool = await get_system_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO trip_events (trip_id, event_type, agent, payload)
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                trip_id,
                event_type,
                agent,
                json.dumps(body),
            )
    except Exception:
        logger.exception(
            "failed to persist trip event %s",
            event_type,
            extra={"trip_id": trip_id, "agent": agent or "system"},
        )


async def log_error(
    trip_id: Optional[str],
    message: str,
    *,
    agent: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    if not message:
        return
    try:
        pool = await get_system_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO trip_errors (trip_id, agent, message, details)
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                trip_id,
                agent,
                message,
                json.dumps(jsonable(details)) if details is not None else None,
            )
    except Exception:
        logger.exception(
            "failed to persist trip error",
            extra={"trip_id": trip_id, "agent": agent or "system"},
        )


async def list_events(trip_id: str) -> list[dict[str, Any]]:
    pool = await get_system_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, trip_id, event_type, agent, payload, created_at
            FROM trip_events
            WHERE trip_id = $1
            ORDER BY created_at ASC, id ASC
            """,
            trip_id,
        )
    return [_event_row(r) for r in rows]


async def list_errors(trip_id: str) -> list[dict[str, Any]]:
    pool = await get_system_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, trip_id, agent, message, details, created_at
            FROM trip_errors
            WHERE trip_id = $1
            ORDER BY created_at ASC, id ASC
            """,
            trip_id,
        )
    return [_error_row(r) for r in rows]


def _event_row(row) -> dict[str, Any]:
    data = dict(row)
    created = data.get("created_at")
    if created is not None:
        data["created_at"] = created.isoformat()
    payload = data.get("payload")
    if isinstance(payload, str):
        try:
            data["payload"] = json.loads(payload)
        except json.JSONDecodeError:
            pass
    return data


def _error_row(row) -> dict[str, Any]:
    data = dict(row)
    created = data.get("created_at")
    if created is not None:
        data["created_at"] = created.isoformat()
    details = data.get("details")
    if isinstance(details, str):
        try:
            data["details"] = json.loads(details)
        except json.JSONDecodeError:
            pass
    return data
