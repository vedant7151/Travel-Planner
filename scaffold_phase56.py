import os

scaffold = {
    # PHASE 6: TOOLS
    "backend/app/tools/weather.py": '''from langchain_core.tools import tool
import httpx

@tool
async def weather_tool(lat: float, lon: float) -> dict:
    """Fetch weather forecast for coordinates using Open-Meteo."""
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
        )
        return res.json()
''',

    "backend/app/tools/places.py": '''from langchain_core.tools import tool
import httpx

@tool
async def places_tool(query: str) -> list:
    """Search for places/attractions using Nominatim (OpenStreetMap)."""
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"https://nominatim.openstreetmap.org/search?q={query}&format=json"
        )
        return res.json()
''',

    "backend/app/tools/maps.py": '''from langchain_core.tools import tool
import httpx

@tool
async def maps_tool(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> dict:
    """Get driving directions and distance using OSRM."""
    async with httpx.AsyncClient() as client:
        url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=false"
        res = await client.get(url)
        return res.json()
''',

    "backend/app/tools/search.py": '''from langchain_core.tools import tool
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
''',

    "backend/app/tools/__init__.py": '''from .weather import weather_tool
from .places import places_tool
from .maps import maps_tool
from .search import hotel_search_tool, flight_search_tool

ALL_TOOLS = [weather_tool, places_tool, maps_tool, hotel_search_tool, flight_search_tool]
''',

    # PHASE 5: AGENTS
    "backend/app/agents/destination.py": '''from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from app.state.travel_state import TravelState
from app.tools import weather_tool, places_tool

llm = ChatOpenAI(model="gpt-4o")

DESTINATION_PROMPT = """
You are a destination research expert. Given: {user_request}, provide:
1. Top attractions and experiences
2. Weather and packing tips for the travel period
Use the available tools to fetch live data.
"""

async def destination_research_node(state: TravelState) -> TravelState:
    agent = create_react_agent(llm, tools=[places_tool, weather_tool])
    result = await agent.ainvoke({
        "messages": [HumanMessage(content=DESTINATION_PROMPT.format(user_request=state["user_request"]))]
    })
    state["destination_info"] = {"raw_output": result["messages"][-1].content}
    return state
''',

    "backend/app/agents/itinerary.py": '''from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from app.state.travel_state import TravelState
from app.tools import maps_tool

llm = ChatOpenAI(model="gpt-4o")

ITINERARY_PROMPT = """
You are an expert travel itinerary planner.
Using this destination research: {destination_info}
Create a detailed itinerary based on: {user_request}
List out the daily plan.
"""

async def itinerary_planning_node(state: TravelState) -> TravelState:
    agent = create_react_agent(llm, tools=[maps_tool])
    result = await agent.ainvoke({"messages": [
        HumanMessage(content=ITINERARY_PROMPT.format(
            destination_info=state.get("destination_info", {}),
            user_request=state["user_request"]
        ))
    ]})
    state["itinerary"] = {"raw_output": result["messages"][-1].content}
    return state
''',

    "backend/app/agents/accommodation.py": '''from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from app.state.travel_state import TravelState
from app.tools import hotel_search_tool

llm = ChatOpenAI(model="gpt-4o")

ACCOMMODATION_PROMPT = """
Search for accommodation based on this request: {user_request}.
Return the top 5 options.
"""

async def accommodation_node(state: TravelState) -> TravelState:
    agent = create_react_agent(llm, tools=[hotel_search_tool])
    result = await agent.ainvoke({"messages": [
        HumanMessage(content=ACCOMMODATION_PROMPT.format(user_request=state["user_request"]))
    ]})
    state["accommodation_options"] = [{"raw_output": result["messages"][-1].content}]
    return state
''',

    "backend/app/agents/transport.py": '''from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from app.state.travel_state import TravelState
from app.tools import flight_search_tool

llm = ChatOpenAI(model="gpt-4o")

TRANSPORT_PROMPT = """
Search transport options based on: {user_request}.
Return options sorted by price.
"""

async def transport_node(state: TravelState) -> TravelState:
    agent = create_react_agent(llm, tools=[flight_search_tool])
    result = await agent.ainvoke({"messages": [
        HumanMessage(content=TRANSPORT_PROMPT.format(user_request=state["user_request"]))
    ]})
    state["transport_options"] = [{"raw_output": result["messages"][-1].content}]
    return state
'''
}

for filepath, content in scaffold.items():
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

print("Scaffold generation for Phase 5 & 6 complete.")
