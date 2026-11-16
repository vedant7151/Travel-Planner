from app.agents.common import request_dict
from app.agents.enrich import enrich_destination_payload
from app.agents.react import run_react_json
from app.core.logging import logger
from app.core.models import DestinationAgentOutput
from app.core.parse import validate_with_repair
from app.state.travel_state import TravelState
from app.tools import places_tool, weather_tool

PROMPT = """
You are a destination research expert. Use tools; do not invent facts.

User request JSON: {user_request}

Required tool use:
1. Call places_tool with the destination name (and origin context only if useful).
2. If Nominatim returns lat/lon, call weather_tool with those coordinates and
   start_date={start_date}, end_date={end_date} when dates are present.

Return JSON with keys:
- attractions: array of names taken from Nominatim display_name / named results only (or [])
- coordinates: {{"lat": number, "lon": number}} from Nominatim, or null
- nominatim_results: condensed list of {{display_name, lat, lon, type}} from the tool, or []
- weather: Open-Meteo tool payload or null
- packing_tips: derived only from weather tool data, or null
- notes: string or null
- visa_safety_cuisine: null (no live source for these — do not guess)
- tool_errors: array of error strings from tools
"""


async def destination_research_node(state: TravelState) -> dict:
    req = request_dict(state)
    trip_id = state.get("trip_id")
    logger.info(
        "destination agent started",
        extra={"agent": "destination", "trip_id": trip_id},
    )
    parsed, raw, errors, tool_results = await run_react_json(
        PROMPT.format(
            user_request=req,
            start_date=req.get("start_date"),
            end_date=req.get("end_date"),
        ),
        [places_tool, weather_tool],
        agent_name="destination",
        trip_id=trip_id,
    )

    payload = dict(parsed) if isinstance(parsed, dict) else {}
    payload.setdefault("visa_safety_cuisine", None)
    if "nominatim_results" not in payload:
        for item in tool_results:
            content = item.get("content")
            if isinstance(content, dict) and isinstance(content.get("results"), list):
                payload["nominatim_results"] = content["results"][:8]
                break
    if not payload.get("weather"):
        for item in tool_results:
            content = item.get("content")
            if isinstance(content, dict) and "daily" in content:
                payload["weather"] = content
                break

    model, degraded = await validate_with_repair(
        payload, raw, DestinationAgentOutput, agent_name="destination"
    )
    payload = model.model_dump()
    payload["raw_text"] = raw
    if degraded and model.generation_status == "unavailable":
        errors = list(errors) + ["destination: output failed schema validation after repair attempt"]

    if errors:
        payload["failed"] = True
        payload["error"] = "; ".join(str(e) for e in errors)
    payload = await enrich_destination_payload(payload, str(req.get("destination") or ""))
    return {"destination_info": payload, "errors": errors}
