from langchain_core.tools import tool
import httpx

@tool
async def weather_tool(lat: float, lon: float) -> dict:
    """Fetch weather forecast for coordinates using Open-Meteo."""
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
        )
        return res.json()
