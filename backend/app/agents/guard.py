from functools import wraps
from typing import Any, Callable

from app.core.logging import logger
from app.core.serialize import jsonable
from app.db.events import log_error, log_event


def _failure_value(result_key: str, exc: Exception) -> Any:
    marker = {"failed": True, "error": str(exc)}
    if result_key in {"accommodation_options", "transport_options"}:
        return [marker]
    return marker


# Maps TravelState keys to the human-facing section label used in trip status
# reporting (API response and frontend banners).
SECTION_LABELS = {
    "destination_info": "destination",
    "itinerary": "itinerary",
    "accommodation_options": "accommodation",
    "transport_options": "transport",
}


def _is_degraded(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get("failed")) or value.get("generation_status") == "unavailable"
    if isinstance(value, list):
        return any(_is_degraded(item) for item in value)
    return False


def degraded_sections(state: dict) -> list[str]:
    """Section labels whose specialist output is marked failed/unavailable."""
    return [
        label
        for state_key, label in SECTION_LABELS.items()
        if _is_degraded(state.get(state_key))
    ]


def safe_node(agent_name: str, result_key: str):
    """Catch specialist failures, persist them, and still advance graph state."""

    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(state: dict, *args, **kwargs):
            trip_id = state.get("trip_id")
            await log_event(trip_id, "node_start", agent=agent_name)
            try:
                result = await fn(state, *args, **kwargs)
            except Exception as exc:
                logger.exception(
                    "%s node crashed",
                    agent_name,
                    extra={"agent": agent_name, "trip_id": trip_id},
                )
                await log_error(
                    trip_id,
                    str(exc),
                    agent=agent_name,
                    details={"type": type(exc).__name__},
                )
                await log_event(
                    trip_id,
                    "node_error",
                    agent=agent_name,
                    payload={"error": str(exc)},
                )
                return {
                    result_key: _failure_value(result_key, exc),
                    "errors": [f"{agent_name}: {exc}"],
                }

            errors = result.get("errors") or []
            for message in errors:
                await log_error(trip_id, str(message), agent=agent_name)
            await log_event(
                trip_id,
                "node_end",
                agent=agent_name,
                payload={"updated": list(result.keys()), "result": jsonable(result)},
            )
            return result

        return wrapper

    return decorator
