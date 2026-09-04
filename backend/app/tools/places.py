from langchain_core.tools import tool
import httpx

@tool
async def places_tool(query: str) -> list:
    """Search for places/attractions using Nominatim (OpenStreetMap)."""
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"https://nominatim.openstreetmap.org/search?q={query}&format=json"
        )
        return res.json()
