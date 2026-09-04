from langchain_core.tools import tool
import httpx

@tool
async def maps_tool(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> dict:
    """Get driving directions and distance using OSRM."""
    async with httpx.AsyncClient() as client:
        url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=false"
        res = await client.get(url)
        return res.json()
