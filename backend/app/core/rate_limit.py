from typing import Awaitable, Callable, TypeVar

from slowapi import Limiter
from slowapi.util import get_remote_address
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_random_exponential

from app.core.config import REDIS_URL
from app.core.redis import provider_rate_gate

T = TypeVar("T")


class ProviderRateLimited(Exception):
    pass


api_limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri=REDIS_URL or "memory://",
)


async def provider_call(
    provider: str,
    limit: int,
    window_seconds: int,
    call: Callable[[], Awaitable[T]],
    *,
    wait_for_slot: bool = False,
    units: int = 1,
) -> T:
    allowed = await provider_rate_gate(
        provider, limit,         window_seconds, wait_for_slot=wait_for_slot, units=units
    )
    if not allowed:
        raise ProviderRateLimited(f"{provider} rate limit exhausted")
    return await call()


def retry_provider_call():
    def should_retry(exc: BaseException) -> bool:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        return status_code == 429 or status_code is not None and status_code >= 500

    return retry(
        retry=retry_if_exception(should_retry),
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=1, max=8),
        reraise=True,
    )
