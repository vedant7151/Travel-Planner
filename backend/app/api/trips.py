from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request

from app.agents.graph import complete_planning
from app.core.auth import CurrentUser, get_current_user, require_role
from app.core.logging import logger
from app.core.rate_limit import api_limiter
from app.core.schemas import PreferencesUpdate, TripRequest, TripResponse, TripStatus
from app.db.events import list_errors, list_events, log_event
from app.db.postgres import (
    create_trip,
    get_trip,
    list_all_trips,
    list_trips,
    update_trip_request,
)

router = APIRouter()


def _parse_trip_id(trip_id: str) -> str:
    try:
        return str(UUID(trip_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid trip_id") from exc


def _to_response(row: dict) -> TripResponse:
    plan = row.get("final_plan") or {}
    structured = plan.get("structured") if isinstance(plan, dict) else None
    itinerary = None
    accommodation = None
    transport = None
    if isinstance(structured, dict):
        itinerary = structured.get("itinerary")
        accommodation = structured.get("accommodation")
        transport = structured.get("transport")
        if isinstance(itinerary, list):
            itinerary = {"days": itinerary}
        if isinstance(accommodation, dict):
            accommodation = [accommodation]
        if isinstance(transport, dict):
            transport = [transport]
        if itinerary is not None and not isinstance(itinerary, dict):
            itinerary = {"text": itinerary} if not isinstance(itinerary, list) else {"days": itinerary}
        if accommodation is not None and not isinstance(accommodation, list):
            accommodation = [accommodation]
        if transport is not None and not isinstance(transport, list):
            transport = [transport]
    total_cost = None
    currency = None
    map_url = None
    image_url = None
    places = None
    degraded_sections = None
    if isinstance(structured, dict):
        raw_cost = structured.get("total_estimated_cost")
        if isinstance(raw_cost, (int, float)):
            total_cost = float(raw_cost)
        currency = structured.get("currency")
        map_url = structured.get("map_url")
        image_url = structured.get("image_url")
        places = structured.get("places") if isinstance(structured.get("places"), list) else None
        degraded_sections = structured.get("degraded_sections")
    if degraded_sections is None and isinstance(plan, dict):
        degraded_sections = plan.get("degraded_sections")
    if not isinstance(degraded_sections, list):
        degraded_sections = None
    return TripResponse(
        trip_id=row["id"],
        status=row["status"],
        user_id=row.get("user_id"),
        request=row.get("request"),
        itinerary=itinerary if isinstance(itinerary, dict) else None,
        accommodation=accommodation if isinstance(accommodation, list) else None,
        transport=transport if isinstance(transport, list) else None,
        total_estimated_cost=total_cost,
        currency=currency if isinstance(currency, str) else None,
        map_url=map_url if isinstance(map_url, str) else None,
        image_url=image_url if isinstance(image_url, str) else None,
        places=places,
        final_plan=plan if plan else None,
        degraded_sections=degraded_sections,
        error=row.get("error"),
        created_at=row.get("created_at"),
    )


async def _background_plan(trip_id: str) -> None:
    try:
        await complete_planning(trip_id)
    except Exception:
        logger.exception("background planning failed for %s", trip_id)


@router.post("/plan", response_model=TripResponse)
@api_limiter.limit("5/minute")
async def plan_trip(
    request: Request,
    trip_request: TripRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
    wait: bool = Query(
        False,
        description="If true, run the agent graph before returning. Otherwise plan in the background.",
    ),
):
    if trip_request.end_date < trip_request.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    trip_id = str(uuid4())
    request_data = trip_request.model_dump(mode="json")
    request_data["user_id"] = current_user.id
    try:
        row = await create_trip(trip_id, current_user.id, request_data)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not save trip: {exc}") from exc
    await log_event(
        trip_id,
        "trip_created",
        payload={"request": request_data, "status": "queued"},
    )
    if wait:
        await complete_planning(trip_id)
        row = await get_trip(trip_id) or row
        return _to_response(row)
    background_tasks.add_task(_background_plan, trip_id)
    return _to_response(row)


@router.post("/{trip_id}/run", response_model=TripResponse)
async def run_trip_plan(trip_id: str, current_user: CurrentUser = Depends(get_current_user)):
    trip_id = _parse_trip_id(trip_id)
    row = await get_trip(trip_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trip not found")
    await complete_planning(trip_id)
    updated = await get_trip(trip_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Trip not found")
    return _to_response(updated)


@router.get("/history", response_model=list[TripResponse])
async def trip_history(
    user_id: UUID = Query(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    logger.info("trip history requested by user %s for user_id %s", current_user.id, user_id)
    # This is a requested history filter, not an authorization check; RLS enforces ownership.
    rows = await list_trips(str(user_id))
    return [_to_response(r) for r in rows]


@router.get("/admin/all", response_model=list[TripResponse])
async def admin_trip_list(
    current_user: CurrentUser = Depends(require_role("admin")),
):
    logger.info("admin trip list requested by user %s", current_user.id)
    return [_to_response(row) for row in await list_all_trips()]


@router.get("/{trip_id}/events")
async def get_trip_events(
    trip_id: str, current_user: CurrentUser = Depends(get_current_user)
):
    logger.info("trip events requested by user %s", current_user.id)
    trip_id = _parse_trip_id(trip_id)
    row = await get_trip(trip_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trip not found")
    return {"trip_id": trip_id, "events": await list_events(trip_id)}


@router.get("/{trip_id}/errors")
async def get_trip_errors(
    trip_id: str, current_user: CurrentUser = Depends(get_current_user)
):
    logger.info("trip errors requested by user %s", current_user.id)
    trip_id = _parse_trip_id(trip_id)
    row = await get_trip(trip_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trip not found")
    return {"trip_id": trip_id, "errors": await list_errors(trip_id)}


@router.get("/{trip_id}", response_model=TripResponse)
async def get_trip_plan(
    trip_id: str, current_user: CurrentUser = Depends(get_current_user)
):
    logger.info("trip requested by user %s", current_user.id)
    trip_id = _parse_trip_id(trip_id)
    row = await get_trip(trip_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trip not found")
    return _to_response(row)


@router.get("/{trip_id}/status", response_model=TripStatus)
async def get_trip_status(
    trip_id: str, current_user: CurrentUser = Depends(get_current_user)
):
    logger.info("trip status requested by user %s", current_user.id)
    trip_id = _parse_trip_id(trip_id)
    row = await get_trip(trip_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trip not found")
    return TripStatus(trip_id=row["id"], status=row["status"], error=row.get("error"))


@router.put("/{trip_id}/preferences", response_model=TripResponse)
async def update_preferences(
    trip_id: str,
    body: PreferencesUpdate,
    current_user: CurrentUser = Depends(get_current_user),
):
    logger.info("trip preferences requested by user %s", current_user.id)
    trip_id = _parse_trip_id(trip_id)
    row = await get_trip(trip_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trip not found")
    request = dict(row.get("request") or {})
    request["preferences"] = body.preferences
    updated = await update_trip_request(trip_id, request)
    if not updated:
        raise HTTPException(status_code=404, detail="Trip not found")
    await log_event(
        trip_id,
        "preferences_updated",
        payload={"preferences": body.preferences},
    )
    return _to_response(updated)
