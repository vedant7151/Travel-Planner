import asyncio

from ddgs import DDGS
from langchain_core.tools import tool

from app.core.config import DDG_MAX_RESULTS, DDG_REGION


def _search(query: str) -> list:
    results: list = []
    with DDGS() as ddgs:
        rows = ddgs.text(
            query,
            region=DDG_REGION,
            max_results=max(1, DDG_MAX_RESULTS),
        )
        results = list(rows or [])
    return results


@tool
async def hotel_search_tool(query: str) -> dict:
    """Web search for hotels via DuckDuckGo. Snippets only — not a booking API."""
    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(_search, f"hotels in {query}"),
            timeout=30,
        )
        if not results:
            return {"error": "DuckDuckGo returned no hotel results", "query": query, "results": []}
        return {"query": query, "results": results}
    except Exception as exc:
        return {"error": f"DuckDuckGo hotel search failed: {exc}", "query": query, "results": []}


@tool
async def flight_search_tool(query: str) -> dict:
    """Web search for flights/trains/buses via DuckDuckGo. Snippets only."""
    try:
        results = await asyncio.wait_for(asyncio.to_thread(_search, query), timeout=30)
        if not results:
            return {
                "error": "DuckDuckGo returned no transport results",
                "query": query,
                "results": [],
            }
        return {"query": query, "results": results}
    except Exception as exc:
        return {
            "error": f"DuckDuckGo transport search failed: {exc}",
            "query": query,
            "results": [],
        }
