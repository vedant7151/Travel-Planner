from typing import TypedDict, Annotated, List, Optional
import operator

class TravelState(TypedDict):
    trip_id: str
    user_request: dict
    destination_info: Optional[dict]
    itinerary: Optional[dict]
    accommodation_options: Optional[List]
    transport_options: Optional[List]
    final_plan: Optional[dict]
    messages: Annotated[List, operator.add]
    errors: Annotated[List, operator.add]
    next_agent: Optional[str]
