from langchain_core.prompts import ChatPromptTemplate

from app.core.llm import invoke_llm
from app.core.logging import logger
from app.db.events import log_error, log_event
from app.state.travel_state import TravelState

ROUTE_MAP = {
    "destination": "destination",
    "itinerary": "itinerary",
    "accommodation": "accommodation",
    "transport": "transport",
    "aggregate": "aggregator",
    "end": "end",
}

SUPERVISOR_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a travel planning supervisor.
Reply with ONLY one token: destination, itinerary, accommodation, transport, aggregate, or end.

Rules:
- destination first if destination_info is missing
- itinerary only after destination_info exists
- accommodation and transport after destination_info exists
- aggregate only when destination, itinerary, accommodation, and transport are all present
- end only when final_plan is present

Do not invent trip content.""",
        ),
        ("human", "State summary:\n{state_summary}"),
    ]
)


def _filled(value: object) -> bool:
    if value in (None, "", [], {}):
        return False
    if isinstance(value, dict) and value.get("failed"):
        return True
    if isinstance(value, list) and any(
        isinstance(item, dict) and item.get("failed") for item in value
    ):
        return True
    return True


def fallback_route(state: TravelState) -> str:
    if not _filled(state.get("destination_info")):
        return "destination"
    if not _filled(state.get("itinerary")):
        return "itinerary"
    if not _filled(state.get("accommodation_options")):
        return "accommodation"
    if not _filled(state.get("transport_options")):
        return "transport"
    if not _filled(state.get("final_plan")):
        return "aggregate"
    return "end"


def is_legal_route(state: TravelState, choice: str) -> bool:
    if choice not in ROUTE_MAP:
        return False
    if choice == "end":
        return fallback_route(state) == "end"
    if choice == "destination":
        return not _filled(state.get("destination_info"))
    if choice == "itinerary":
        return _filled(state.get("destination_info")) and not _filled(state.get("itinerary"))
    if choice == "accommodation":
        return _filled(state.get("destination_info")) and not _filled(
            state.get("accommodation_options")
        )
    if choice == "transport":
        return _filled(state.get("destination_info")) and not _filled(
            state.get("transport_options")
        )
    if choice == "aggregate":
        return fallback_route(state) == "aggregate"
    return False


def summarise_state(state: TravelState) -> str:
    req = state.get("user_request") or {}
    return (
        f"trip_id={state.get('trip_id')}\n"
        f"destination={req.get('destination')}\n"
        f"origin={req.get('origin')}\n"
        f"has_destination_info={_filled(state.get('destination_info'))}\n"
        f"has_itinerary={_filled(state.get('itinerary'))}\n"
        f"has_accommodation={_filled(state.get('accommodation_options'))}\n"
        f"has_transport={_filled(state.get('transport_options'))}\n"
        f"has_final_plan={_filled(state.get('final_plan'))}\n"
        f"errors={state.get('errors')}"
    )


def _parse_token(raw: str) -> str:
    text = (raw or "").strip().lower().replace("'", "").replace('"', "")
    text = text.replace("`", "")
    if not text:
        return ""
    token = text.replace("-", " ").replace("_", " ").split()[0]
    aliases = {"aggregator": "aggregate", "hotel": "accommodation", "flight": "transport"}
    return aliases.get(token, token)


async def supervisor_node(state: TravelState) -> dict:
    nxt = fallback_route(state)
    try:
        messages = SUPERVISOR_PROMPT.format_messages(
            state_summary=summarise_state(state)
        )
        response = await invoke_llm(messages)
        content = response.content
        if isinstance(content, list):
            content = " ".join(str(part) for part in content)
        token = _parse_token(str(content))
        if is_legal_route(state, token):
            nxt = token
    except Exception as exc:
        logger.warning("supervisor llm failed, using fallback: %s", exc)
        nxt = fallback_route(state)
        await log_error(
            state.get("trip_id"),
            f"supervisor llm failed: {exc}",
            agent="supervisor",
            details={"type": type(exc).__name__},
        )

    await log_event(
        state.get("trip_id"),
        "supervisor_route",
        agent="supervisor",
        payload={"next_agent": nxt},
    )
    logger.info(
        "supervisor routed to %s",
        nxt,
        extra={"agent": "supervisor", "trip_id": state.get("trip_id")},
    )
    return {"next_agent": nxt}


def route_to_agents(state: TravelState) -> str:
    nxt = state.get("next_agent") or fallback_route(state)
    if not is_legal_route(state, nxt):
        nxt = fallback_route(state)
    return nxt
