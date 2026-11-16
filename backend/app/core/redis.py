import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from upstash_redis import AsyncRedis

from app.core.config import UPSTASH_REDIS_REST_TOKEN, UPSTASH_REDIS_REST_URL
from app.core.logging import logger

_client: AsyncRedis | None = None
_disabled = False


class RedisRateLimitExceeded(Exception):
    pass


def _get_client() -> AsyncRedis | None:
    global _client, _disabled
    if _disabled:
        return None
    if _client is None:
        if not UPSTASH_REDIS_REST_URL or not UPSTASH_REDIS_REST_TOKEN:
            _disabled = True
            logger.warning("Upstash Redis is not configured; continuing without cache or locks")
            return None
        _client = AsyncRedis(UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN)
    return _client


async def cache_get(key: str) -> Any | None:
    client = _get_client()
    if client is None:
        return None
    try:
        value = await client.get(key)
        if value is None:
            return None
        logger.info("Redis cache hit: %s", key)
        return json.loads(value) if isinstance(value, str) else value
    except Exception as exc:
        logger.warning("Redis cache read failed for %s: %s", key, exc)
        return None


async def cache_set(key: str, value: Any, ttl_seconds: int) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        await client.set(key, json.dumps(value), ex=ttl_seconds)
        return True
    except Exception as exc:
        logger.warning("Redis cache write failed for %s: %s", key, exc)
        return False


async def consume_rate_limit(
    key: str,
    limit: int,
    window_seconds: int,
    *,
    wait_for_slot: bool = False,
    units: int = 1,
) -> bool:
    client = _get_client()
    if client is None:
        return True
    while True:
        try:
            if wait_for_slot:
                acquired = await client.set(
                    key,
                    "1",
                    nx=True,
                    px=window_seconds * 1000,
                )
                if acquired is True:
                    return True
                await asyncio.sleep(0.1)
                continue
            count = int(await client.incrby(key, max(1, units)))
            if count == 1:
                await client.expire(key, window_seconds)
            if count <= limit:
                return True
            return False
        except Exception as exc:
            logger.warning("Redis rate-limit check failed for %s: %s", key, exc)
            return True


async def provider_rate_gate(
    provider: str,
    limit: int,
    window_seconds: int,
    *,
    wait_for_slot: bool = False,
    units: int = 1,
) -> bool:
    return await consume_rate_limit(
        f"travel:ratelimit:provider:{provider}",
        limit,
        window_seconds,
        wait_for_slot=wait_for_slot,
        units=units,
    )


@asynccontextmanager
async def distributed_lock(key: str, ttl_seconds: int) -> AsyncIterator[bool]:
    client = _get_client()
    if client is None:
        yield True
        return

    token = str(uuid.uuid4())
    acquired = False
    try:
        acquired = (await client.set(key, token, nx=True, ex=ttl_seconds)) is True
    except Exception as exc:
        logger.warning("Redis lock acquisition failed for %s: %s", key, exc)
        yield True
        return

    if not acquired:
        yield False
        return

    try:
        yield True
    finally:
        try:
            await client.eval(
                "if redis.call('get', KEYS[1]) == ARGV[1] then "
                "return redis.call('del', KEYS[1]) else return 0 end",
                keys=[key],
                args=[token],
            )
        except Exception as exc:
            logger.warning("Redis lock release failed for %s: %s", key, exc)


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
