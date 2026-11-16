from app.core.cache_keys import fx_key
from app.core.redis import cache_get, cache_set
from app.tools.client import get_json


async def fx_rates(base: str) -> dict[str, float]:
    code = (base or "USD").upper()
    cached = await cache_get(fx_key(code))
    if isinstance(cached, dict):
        return {str(k): float(v) for k, v in cached.items()}
    data = await get_json(f"https://open.er-api.com/v6/latest/{code}")
    if not isinstance(data, dict) or data.get("result") == "error":
        raise RuntimeError(data.get("error-type") if isinstance(data, dict) else "fx lookup failed")
    rates = data.get("rates") or {}
    cleaned = {str(k).upper(): float(v) for k, v in rates.items() if isinstance(v, (int, float))}
    cleaned[code] = 1.0
    await cache_set(fx_key(code), cleaned, 60 * 60)
    return cleaned


async def convert_amount(amount: float, from_currency: str, to_currency: str) -> float | None:
    src = (from_currency or "USD").upper()
    dst = (to_currency or "USD").upper()
    if src == dst:
        return round(float(amount), 2)
    try:
        rates = await fx_rates(src)
        rate = rates.get(dst)
        if rate is None:
            return None
        return round(float(amount) * rate, 2)
    except Exception:
        return None
