import httpx

from app.core.config import (
    DDG_MAX_RESULTS,
    HTTP_TIMEOUT_SECONDS,
    NOMINATIM_BASE_URL,
    OPEN_METEO_BASE_URL,
    OSRM_BASE_URL,
)
from app.core.rate_limit import provider_call, retry_provider_call

_client: httpx.AsyncClient | None = None


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)
    return _client


async def close_http_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def get_json(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
) -> dict | list:
    provider, limit, window, wait = _provider_policy(url)

    async def _request():
        client = await get_client()
        res = await client.get(url, params=params, headers=headers)
        res.raise_for_status()
        return res.json()

    @retry_provider_call()
    async def request():
        return await provider_call(provider, limit, window, _request, wait_for_slot=wait)

    return await request()


def _provider_policy(url: str) -> tuple[str, int, int, bool]:
    if url.startswith(NOMINATIM_BASE_URL):
        return "nominatim", 1, 1, True
    if url.startswith(OSRM_BASE_URL):
        return "osrm", 30, 60, False
    if url.startswith(OPEN_METEO_BASE_URL):
        return "open-meteo", 30, 60, False
    if "api.openverse.org" in url:
        return "openverse", 30, 60, False
    if "open.er-api.com" in url:
        return "fx", 30, 60, False
    if "duckduckgo" in url or "ddgs" in url:
        return "ddg", max(1, DDG_MAX_RESULTS), 60, False
    return "external", 60, 60, False
