from langchain_core.tools import tool
from duckduckgo_search import DDGS

@tool
async def hotel_search_tool(query: str) -> list:
    """Search for hotels using DuckDuckGo Search."""
    results = DDGS().text(f"hotels in {query}", max_results=5)
    return results

@tool
async def flight_search_tool(query: str) -> list:
    """Search for flights using DuckDuckGo Search."""
    results = DDGS().text(f"flights to {query}", max_results=5)
    return results
