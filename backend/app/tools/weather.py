from langchain_core.tools import tool

from app.core.config import OPEN_METEO_BASE_URL
from app.tools.client import get_json


@tool
async def weather_tool(
    lat: float,
    lon: float,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Daily forecast from Open-Meteo (free, no API key). Optional ISO dates YYYY-MM-DD."""
    params: dict = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode",
        "timezone": "auto",
    }
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    try:
        data = await get_json(OPEN_METEO_BASE_URL, params=params)
        if isinstance(data, dict) and data.get("error"):
            return {"error": data.get("reason") or data.get("error"), "lat": lat, "lon": lon}
        return data if isinstance(data, dict) else {"error": "Open-Meteo returned a non-object", "raw": data}
    except Exception as exc:
        # Forecast API only covers a short horizon; far-future dates return 400.
        if "start_date" in params or "end_date" in params:
            fallback = {
                "latitude": lat,
                "longitude": lon,
                "daily": params["daily"],
                "timezone": "auto",
            }
            try:
                data = await get_json(OPEN_METEO_BASE_URL, params=fallback)
                if isinstance(data, dict) and not data.get("error"):
                    data["note"] = (
                        "Requested travel dates are outside the Open-Meteo forecast "
                        "window; returning the near-term forecast instead."
                    )
                    return data
            except Exception:
                pass
        return {"error": f"Open-Meteo request failed: {exc}", "lat": lat, "lon": lon}
