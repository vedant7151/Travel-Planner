from langchain_core.tools import tool

from app.core.config import OSRM_BASE_URL
from app.geo.map_url import map_url
from app.tools.client import get_json


@tool
async def maps_tool(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
) -> dict:
    """Driving distance/duration via the public OSRM server (free, no API key)."""
    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
    )
    try:
        data = await get_json(url, params={"overview": "false"})
        if not isinstance(data, dict):
            return {"error": "OSRM returned an unexpected payload"}
        if data.get("code") and str(data.get("code")).lower() != "ok":
            return {
                "error": f"OSRM status {data.get('code')}",
                "message": data.get("message"),
            }
        data["start_map_url"] = map_url(start_lat, start_lon)
        data["end_map_url"] = map_url(end_lat, end_lon)
        data["map_url"] = data["end_map_url"]
        return data
    except Exception as exc:
        return {"error": f"OSRM request failed: {exc}"}
