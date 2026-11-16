from app.core.cache_keys import media_key
from app.core.config import NOMINATIM_EMAIL, NOMINATIM_USER_AGENT
from app.core.redis import cache_get, cache_set
from app.tools.client import get_json


def _headers() -> dict:
    ua = NOMINATIM_USER_AGENT
    if NOMINATIM_EMAIL and NOMINATIM_EMAIL not in ua:
        ua = f"{ua} ({NOMINATIM_EMAIL})"
    if "contact" not in ua.lower() and "http" not in ua.lower():
        ua = f"{ua} (educational travel planner)"
    return {"User-Agent": ua, "Accept": "application/json"}


async def place_image_url(query: str) -> str | None:
    """Public Creative Commons image URL for a place (Openverse). No API key."""
    key = (query or "").strip()
    if not key:
        return None
    cached = await cache_get(media_key(key))
    if isinstance(cached, dict) and "url" in cached:
        return cached["url"] if isinstance(cached["url"], str) else None
    try:
        data = await get_json(
            "https://api.openverse.org/v1/images/",
            params={"q": key, "page_size": "1", "mature": "false"},
            headers=_headers(),
        )
        results = data.get("results") if isinstance(data, dict) else None
        url = None
        if isinstance(results, list) and results:
            row = results[0]
            if isinstance(row, dict):
                url = row.get("url") or row.get("thumbnail")
        await cache_set(media_key(key), {"url": url}, 7 * 24 * 60 * 60)
        return url
    except Exception:
        await cache_set(media_key(key), {"url": None}, 7 * 24 * 60 * 60)
        return None
