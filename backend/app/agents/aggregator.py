from typing import Any

from langchain_core.messages import HumanMessage

from app.agents.enrich import finalize_plan_media_and_prices
from app.agents.guard import degraded_sections
from app.core.llm import invoke_llm
from app.core.logging import logger
from app.core.models import AggregatorPlanOutput
from app.core.parse import parse_json_content, validate_with_repair
from app.db.events import log_error, log_event
from app.db.postgres import save_final_plan
from app.state.travel_state import TravelState

ALL_SECTIONS = {"destination", "itinerary", "accommodation", "transport"}


def compute_trip_status(
    sections: list[str], aggregator_status: str, has_errors: bool
) -> str:
    """completed: everything succeeded. partial: a usable plan exists but some
    section degraded. failed: every specialist degraded and the aggregator
    itself could not be generated, i.e. there is nothing usable to show.
    """
    if aggregator_status == "ok" and not sections and not has_errors:
        return "completed"
    if aggregator_status == "unavailable" and set(sections) >= ALL_SECTIONS:
        return "failed"
    return "partial"

PROMPT = """
You are a senior travel consultant. Combine ONLY the specialist outputs below
into one plan. Do not invent hotels, flights, prices, attractions, or totals
that are not present in the inputs. If a section is missing or a tool failed,
say so explicitly in that field (do not use null) and record it in warnings.

User request: {user_request}
Destination research: {destination_info}
Itinerary: {itinerary}
Accommodation options: {accommodation_options}
Transport options: {transport_options}
Errors from earlier agents: {errors}

Return a single JSON object with keys:
- summary: short string (required, never null; if nothing is available say so explicitly)
- itinerary: object or array copied/summarised from itinerary input
- accommodation: array of options mentioned in accommodation_options only
- transport: array of options mentioned in transport_options only
- budget_notes: qualitative notes only; no fabricated numeric totals (required, never null)
- tips: array of strings grounded in destination research
- warnings: array of strings (include source errors)
- Keep any map_url, image_url, places, and price fields from the specialist outputs.
  Do not invent coordinates, images, or prices.
"""


def _as_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _passthrough(state: TravelState, extra_warnings: list[str]) -> dict[str, Any]:
    warnings = list(state.get("errors") or []) + extra_warnings
    dest = state.get("destination_info")
    if isinstance(dest, dict):
        tool_errors = dest.get("tool_errors")
        if tool_errors:
            warnings.append(str(tool_errors))
    return {
        "itinerary": state.get("itinerary"),
        "accommodation": state.get("accommodation_options"),
        "transport": state.get("transport_options"),
        "warnings": warnings,
    }


def _merge_structured(plan: AggregatorPlanOutput, fallback: dict[str, Any]) -> dict[str, Any]:
    merged = dict(fallback)
    plan_data = plan.model_dump()
    for key in ("itinerary", "accommodation", "transport"):
        value = plan_data.get(key)
        if value:
            merged[key] = value
    merged["summary"] = plan_data["summary"]
    merged["budget_notes"] = plan_data["budget_notes"]
    merged["tips"] = plan_data["tips"]
    combined_warnings = list(fallback.get("warnings") or []) + (plan_data.get("warnings") or [])
    if plan.generation_status != "ok":
        combined_warnings.append(
            f"Aggregator output {plan.generation_status}: schema validation needed a repair pass."
        )
    merged["warnings"] = list(dict.fromkeys(combined_warnings))
    return merged


async def aggregator_node(state: TravelState) -> dict:
    prompt = PROMPT.format(
        user_request=state.get("user_request"),
        destination_info=state.get("destination_info"),
        itinerary=state.get("itinerary"),
        accommodation_options=state.get("accommodation_options"),
        transport_options=state.get("transport_options"),
        errors=state.get("errors"),
    )
    extra_warnings: list[str] = []
    text = ""
    plan: AggregatorPlanOutput
    try:
        response = await invoke_llm(
            [
                HumanMessage(
                    content=prompt
                    + "\n\nRespond with a single JSON object only. No markdown."
                )
            ]
        )
        text = _as_text(response.content)
        payload = parse_json_content(text)
        plan, _degraded = await validate_with_repair(
            payload, text, AggregatorPlanOutput, agent_name="aggregator"
        )
    except Exception as exc:
        logger.exception("aggregator llm failed: %s", exc)
        extra_warnings.append(f"Aggregator LLM failed: {exc}")
        plan = AggregatorPlanOutput.unavailable(f"LLM invocation failed: {exc}")

    structured = _merge_structured(plan, _passthrough(state, extra_warnings))
    structured = await finalize_plan_media_and_prices(state, structured)

    sections = degraded_sections(state)
    if plan.generation_status != "ok":
        sections = sections + ["aggregator"]
    status = compute_trip_status(
        sections, plan.generation_status, has_errors=bool(state.get("errors"))
    )
    structured["degraded_sections"] = sections

    final_plan = {
        # Raw text is only surfaced for debugging once parsing fully failed;
        # a validated/repaired plan should not have garbled JSON leak to users.
        "text": text if plan.generation_status == "unavailable" else None,
        "structured": structured,
        "source_errors": list(state.get("errors") or []),
        "validation_status": plan.generation_status,
        "degraded_sections": sections,
        "status": status,
    }

    trip_id = state.get("trip_id")
    persist_errors: list[str] = []
    if trip_id:
        try:
            await save_final_plan(trip_id, final_plan, status=status)
            await log_event(
                trip_id,
                "final_plan_saved",
                agent="aggregator",
                payload={
                    "structured_keys": list((structured or {}).keys()),
                    "status": status,
                    "degraded_sections": sections,
                },
            )
        except Exception as exc:
            logger.exception("failed to persist final_plan: %s", exc)
            persist_errors.append(f"persist failed: {exc}")
            await log_error(
                trip_id,
                str(exc),
                agent="aggregator",
                details={"type": type(exc).__name__},
            )
            return {"final_plan": final_plan, "errors": persist_errors}
    return {"final_plan": final_plan}
