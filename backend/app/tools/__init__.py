from .maps import maps_tool
from .places import places_tool
from .search import flight_search_tool, hotel_search_tool
from .weather import weather_tool

ALL_TOOLS = [
    weather_tool,
    places_tool,
    maps_tool,
    hotel_search_tool,
    flight_search_tool,
]

__all__ = [
    "ALL_TOOLS",
    "weather_tool",
    "places_tool",
    "maps_tool",
    "hotel_search_tool",
    "flight_search_tool",
]
