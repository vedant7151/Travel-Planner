from fastapi import APIRouter
from app.core.schemas import TripRequest, TripResponse

router = APIRouter()

@router.post("/plan", response_model=TripResponse)
async def plan_trip(request: TripRequest):
    return {"trip_id": "123", "status": "queued"}
