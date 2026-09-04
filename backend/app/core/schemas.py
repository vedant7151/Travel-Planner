from pydantic import BaseModel
from typing import Optional, List

class TripRequest(BaseModel):
    user_id: str
    destination: str
    start_date: str
    end_date: str
    budget_usd: float
    travellers: int
    preferences: Optional[dict] = {}

class TripResponse(BaseModel):
    trip_id: str
    status: str
    itinerary: Optional[dict] = None
    accommodation: Optional[List[dict]] = None
    transport: Optional[List[dict]] = None
    total_estimated_cost: Optional[float] = None
