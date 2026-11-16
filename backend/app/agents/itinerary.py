from app.agents.common import extract_coords, request_dict, trip_length_days
from app.agents.enrich import enrich_itinerary
from app.agents.react import run_react_json
from app.core.logging import logger
from app.core.models import ItineraryAgentOutput
from app.core.parse import validate_with_repair
from app.state.travel_state import TravelState
from app.tools import maps_tool

PROMPT = """
You are an expert itinerary planner. Use maps_tool only for travel time between
known coordinates. Do not invent attractions that are not in destination research.

User request: {user_request}
Number of days: {num_days}
Destination research: {destination_info}
Known coordinates (lat, lon) if any: {coords}

If you have two distinct coordinate pairs from destination research, call maps_tool
once for a representative leg. If you lack coordinates, skip maps_tool.

Return JSON:
- days: array of length {num_days} (or fewer if dates missing) with keys
  day, morning, afternoon, evening, notes
  Activities must come from destination research attractions/nominatim_results only.
  If there are not enough attractions, repeat area exploration and say so in notes.
- travel_legs: array of {{from, to, duration_seconds, distance_meters}} from maps_tool, or []
- warnings: array
"""


async def itinerary_planning_node(state: TravelState) -> dict:
    req = request_dict(state)
    dest = state.get("destination_info")
    coords = extract_coords(dest)
    num_days = trip_length_days(req)
    trip_id = state.get("trip_id")
    logger.info(
        "itinerary agent started",
        extra={"agent": "itinerary", "trip_id": trip_id},
    )
    parsed, raw, errors, _tools = await run_react_json(
        PROMPT.format(
            user_request=req,
            destination_info=dest,
            coords=coords,
            num_days=num_days,
        ),
        [maps_tool],
        agent_name="itinerary",
        trip_id=trip_id,
    )

    payload = dict(parsed) if isinstance(parsed, dict) else {}
    payload.setdefault("travel_legs", [])
    if not isinstance(payload.get("days"), list):
        payload["days"] = []
        errors = list(errors) + ["itinerary: days missing from model JSON"]

    model, degraded = await validate_with_repair(
        payload, raw, ItineraryAgentOutput, agent_name="itinerary"
    )
    payload = model.model_dump()
    payload["raw_text"] = raw
    if degraded and model.generation_status == "unavailable":
        errors = list(errors) + ["itinerary: output failed schema validation after repair attempt"]

    if errors:
        payload["failed"] = True
        payload["error"] = "; ".join(str(e) for e in errors)
    payload = await enrich_itinerary(
        payload, dest if isinstance(dest, dict) else None, str(req.get("destination") or "")
    )
    return {"itinerary": payload, "errors": errors}
