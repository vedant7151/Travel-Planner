from app.agents.common import request_dict
from app.agents.enrich import enrich_listing, location_map_url
from app.agents.react import ddg_listings, run_react_json
from app.core.logging import logger
from app.core.models import TransportAgentOutput
from app.core.money import normalize_currency
from app.core.parse import validate_with_repair
from app.state.travel_state import TravelState
from app.tools import flight_search_tool

PROMPT = """
You search transport using flight_search_tool only. Do not invent schedules, fares,
airlines, or booking links that are not in the snippets. Missing fields must be null.

User request: {user_request}

Call flight_search_tool with a query such as:
"flights trains buses from {origin} to {destination} departing {start_date} returning {end_date} {travellers} passengers"

If origin is missing, search "transport to {destination} on {start_date}".

Return JSON:
- options: array of {{title, snippet, href, mode_if_stated}} copied from snippets
- query_used: the query you passed to the tool
- warnings: array
"""


def _options_from_parse(parsed: object, listings: list[dict], raw: str) -> list:
    if isinstance(parsed, dict) and isinstance(parsed.get("options"), list) and parsed["options"]:
        cleaned = []
        for item in parsed["options"]:
            if isinstance(item, dict):
                cleaned.append(
                    {
                        "title": item.get("title"),
                        "snippet": item.get("snippet"),
                        "href": item.get("href"),
                        "mode_if_stated": item.get("mode_if_stated"),
                        "stated_price_or_null": item.get("stated_price_or_null"),
                        "source": item.get("source") or "model_summary",
                    }
                )
        if cleaned:
            return cleaned
    if isinstance(parsed, list) and parsed:
        return parsed
    mapped = []
    for row in listings:
        mapped.append(
            {
                "title": row.get("title"),
                "snippet": row.get("snippet"),
                "href": row.get("href"),
                "mode_if_stated": None,
                "stated_price_or_null": None,
                "source": "duckduckgo",
            }
        )
    if mapped:
        return mapped
    if raw:
        return [{"text": raw, "stated_price_or_null": None}]
    return []


async def transport_node(state: TravelState) -> dict:
    req = request_dict(state)
    trip_id = state.get("trip_id")
    logger.info(
        "transport agent started",
        extra={"agent": "transport", "trip_id": trip_id},
    )
    parsed, raw, errors, tool_results = await run_react_json(
        PROMPT.format(
            user_request=req,
            origin=req.get("origin") or "unspecified origin",
            destination=req.get("destination"),
            start_date=req.get("start_date"),
            end_date=req.get("end_date"),
            travellers=req.get("travellers"),
        ),
        [flight_search_tool],
        agent_name="transport",
        trip_id=trip_id,
    )
    listings = ddg_listings(tool_results)
    model, degraded = await validate_with_repair(
        parsed if isinstance(parsed, dict) else None,
        raw,
        TransportAgentOutput,
        agent_name="transport",
    )
    if degraded and model.generation_status == "unavailable":
        errors = list(errors) + ["transport: output failed schema validation after repair attempt"]
    validated = model.model_dump()
    if validated.get("warnings"):
        errors = list(errors) + [str(validated["warnings"])]
    options = _options_from_parse(validated, listings, raw)
    dest = state.get("destination_info") if isinstance(state.get("destination_info"), dict) else {}
    dest_map = location_map_url(dest, str(req.get("destination") or ""))
    dest_image = dest.get("image_url") if dest else None
    currency = normalize_currency(req.get("currency"))
    if options:
        options = [
            await enrich_listing(row, currency, dest_map, dest_image) if isinstance(row, dict) else row
            for row in options
        ]
    if not options:
        options = [{"failed": True, "error": "; ".join(errors) or "no live search snippets"}]
    return {"transport_options": options, "errors": errors}
