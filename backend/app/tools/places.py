from langchain_core.tools import tool

from app.core.cache_keys import geocode_key
from app.core.config import (
    NOMINATIM_BASE_URL,
    NOMINATIM_EMAIL,
    NOMINATIM_RESULT_LIMIT,
    NOMINATIM_USER_AGENT,
)
from app.core.redis import cache_get, cache_set
from app.geo.map_url import map_url
from app.tools.client import get_json


def _nominatim_headers() -> dict:
    ua = NOMINATIM_USER_AGENT
    if NOMINATIM_EMAIL and NOMINATIM_EMAIL not in ua:
        ua = f"{ua} ({NOMINATIM_EMAIL})"
    return {"User-Agent": ua, "Accept-Language": "en"}


@tool
async def places_tool(query: str) -> dict:
    """Geocode a place via Nominatim/OSM. Free; requires a descriptive User-Agent."""
    normalized_query = " ".join((query or "").casefold().split())
    cached = await cache_get(geocode_key(normalized_query))
    if isinstance(cached, dict):
        return cached
    params: dict = {
        "q": query,
        "format": "json",
        "limit": NOMINATIM_RESULT_LIMIT,
        "addressdetails": 1,
    }
    if NOMINATIM_EMAIL:
        params["email"] = NOMINATIM_EMAIL
    try:
        data = await get_json(
            f"{NOMINATIM_BASE_URL}/search",
            params=params,
            headers=_nominatim_headers(),
        )
        if not isinstance(data, list):
            return {"error": "Nominatim returned an unexpected payload", "query": query, "results": []}
        if not data:
            return {"error": "Nominatim returned no results", "query": query, "results": []}
        results = []
        for row in data:
            if isinstance(row, dict):
                item = dict(row)
                try:
                    item["map_url"] = map_url(item["lat"], item["lon"])
                except (KeyError, TypeError, ValueError):
                    pass
                results.append(item)
            else:
                results.append(row)
        response = {"query": query, "results": results}
        await cache_set(geocode_key(normalized_query), response, 7 * 24 * 60 * 60)
        return response
    except Exception as exc:
        return {"error": f"Nominatim request failed: {exc}", "query": query, "results": []}
