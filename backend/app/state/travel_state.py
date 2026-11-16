import operator
from typing import Annotated, Any, Optional, TypedDict


class TravelState(TypedDict, total=False):
    """Shared LangGraph state. Reducers only on append-only lists."""

    trip_id: str
    user_request: dict[str, Any]
    destination_info: Optional[dict[str, Any]]
    itinerary: Optional[dict[str, Any]]
    accommodation_options: Optional[list]
    transport_options: Optional[list]
    final_plan: Optional[dict[str, Any]]
    messages: Annotated[list, operator.add]
    errors: Annotated[list, operator.add]
    next_agent: Optional[str]
