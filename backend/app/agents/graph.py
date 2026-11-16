from langgraph.graph import END, START, StateGraph

from app.agents.accommodation import accommodation_node
from app.agents.aggregator import aggregator_node
from app.agents.destination import destination_research_node
from app.agents.guard import safe_node
from app.agents.itinerary import itinerary_planning_node
from app.agents.supervisor import (
    ROUTE_MAP,
    fallback_route,
    route_to_agents,
    supervisor_node,
)
from app.agents.transport import transport_node
from app.core.cache_keys import trip_lock_key
from app.core.config import SYSTEM_DATABASE_URL, psycopg_conninfo
from app.core.logging import logger
from app.core.redis import distributed_lock
from app.core.serialize import jsonable
from app.db.events import log_error, log_event
from app.db.postgres import get_trip, save_final_plan, update_trip_status
from app.state.travel_state import TravelState

_checkpointer_pool = None
_graph = None


async def _supervisor_guard(state: TravelState) -> dict:
    trip_id = state.get("trip_id")
    await log_event(trip_id, "node_start", agent="supervisor")
    try:
        result = await supervisor_node(state)
        await log_event(
            trip_id,
            "node_end",
            agent="supervisor",
            payload=jsonable(result),
        )
        return result
    except Exception as exc:
        logger.exception("supervisor node crashed")
        await log_error(
            trip_id,
            str(exc),
            agent="supervisor",
            details={"type": type(exc).__name__},
        )
        nxt = fallback_route(state)
        return {"next_agent": nxt, "errors": [f"supervisor: {exc}"]}


def build_graph(checkpointer):
    g = StateGraph(TravelState)
    g.add_node("supervisor", _supervisor_guard)
    g.add_node("destination", safe_node("destination", "destination_info")(destination_research_node))
    g.add_node("itinerary", safe_node("itinerary", "itinerary")(itinerary_planning_node))
    g.add_node(
        "accommodation",
        safe_node("accommodation", "accommodation_options")(accommodation_node),
    )
    g.add_node("transport", safe_node("transport", "transport_options")(transport_node))
    g.add_node("aggregator", safe_node("aggregator", "final_plan")(aggregator_node))

    g.add_edge(START, "supervisor")
    path_map = {key: (END if dest == "end" else dest) for key, dest in ROUTE_MAP.items()}
    g.add_conditional_edges("supervisor", route_to_agents, path_map)
    for node in ["destination", "itinerary", "accommodation", "transport"]:
        g.add_edge(node, "supervisor")
    g.add_edge("aggregator", END)
    return g.compile(checkpointer=checkpointer)


async def init_graph() -> None:
    global _checkpointer_pool, _graph
    if _graph is not None:
        return
    if not SYSTEM_DATABASE_URL:
        raise RuntimeError(
            "SYSTEM_DATABASE_URL is required for the LangGraph Postgres checkpointer."
        )

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg_pool import AsyncConnectionPool

    pool_kwargs = dict(
        conninfo=psycopg_conninfo(SYSTEM_DATABASE_URL),
        min_size=1,
        max_size=5,
        # Supabase transaction-mode pgbouncer cannot retain prepared
        # statements between transactions.
        kwargs={"autocommit": True, "prepare_threshold": None},
    )
    try:
        _checkpointer_pool = AsyncConnectionPool(**pool_kwargs, open=False)
        await _checkpointer_pool.open()
    except TypeError:
        _checkpointer_pool = AsyncConnectionPool(**pool_kwargs)
    checkpointer = AsyncPostgresSaver(_checkpointer_pool)
    await checkpointer.setup()
    async with _checkpointer_pool.connection() as conn:
        for table in (
            "checkpoints",
            "checkpoint_blobs",
            "checkpoint_writes",
            "checkpoint_migrations",
        ):
            await conn.execute(
                f"ALTER TABLE IF EXISTS public.{table} DISABLE ROW LEVEL SECURITY"
            )
    _graph = build_graph(checkpointer)
    logger.info("langgraph compiled with Supabase Postgres checkpointer")


async def close_graph() -> None:
    global _checkpointer_pool, _graph
    _graph = None
    if _checkpointer_pool is not None:
        await _checkpointer_pool.close()
        _checkpointer_pool = None


def get_graph():
    if _graph is None:
        raise RuntimeError("Graph is not initialized. Call init_graph() on startup.")
    return _graph


def _event_payload(node_name: str, payload: object) -> dict:
    keys = list(payload.keys()) if isinstance(payload, dict) else []
    return {"event": "node", "node": node_name, "updated": keys}


async def complete_planning(trip_id: str) -> list[dict]:
    """Run the graph to completion and return streamed events."""
    events: list[dict] = []
    async for update in run_planning_graph(trip_id):
        events.append(update)
    return events


async def run_planning_graph(trip_id: str):
    async with distributed_lock(trip_lock_key(trip_id), 30 * 60) as acquired:
        if not acquired:
            logger.warning("trip %s is already being planned", trip_id)
            yield {"event": "error", "status": "locked", "message": "Trip is already being planned"}
            return
        async for update in _run_planning_graph(trip_id):
            yield update


async def _run_planning_graph(trip_id: str):
    trip = await get_trip(trip_id)
    if not trip:
        await log_error(None, f"trip not found: {trip_id}", agent="graph")
        yield {"event": "error", "message": "trip not found"}
        return

    if trip["status"] == "completed" and trip.get("final_plan"):
        yield {"event": "done", "status": "completed", "final_plan": trip["final_plan"]}
        return

    await update_trip_status(trip_id, "running")
    await log_event(trip_id, "status", payload={"status": "running"})
    yield {"event": "status", "status": "running"}

    graph = get_graph()
    thread_id = trip_id
    if trip["status"] == "failed":
        thread_id = f"{trip_id}-rerun"

    initial: TravelState = {
        "trip_id": trip_id,
        "user_request": trip["request"] or {},
        "messages": [],
        "errors": [],
    }
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 25,
    }
    try:
        snapshot = await graph.aget_state(config)
        resume = bool(snapshot and snapshot.values and snapshot.next)
        stream_input = None if resume else initial
        await log_event(
            trip_id,
            "graph_start",
            payload={"thread_id": thread_id, "resume": resume},
        )

        async for update in graph.astream(stream_input, config, stream_mode="updates"):
            if not isinstance(update, dict):
                continue
            for node_name, payload in update.items():
                await log_event(
                    trip_id,
                    "graph_update",
                    agent=str(node_name),
                    payload={"updated": list(payload.keys()) if isinstance(payload, dict) else []},
                )
                yield _event_payload(str(node_name), payload)

        snapshot = await graph.aget_state(config)
        values = snapshot.values if snapshot else {}
        state_errors = values.get("errors") or []
        for message in state_errors:
            await log_error(trip_id, str(message), agent="graph")

        final_plan = values.get("final_plan")
        if isinstance(final_plan, dict) and final_plan.get("structured"):
            # aggregator_node already computed status/degraded_sections from
            # the explicit degraded markers on each section; reuse it rather
            # than assuming "completed" just because a final_plan exists.
            status = final_plan.get("status") or "completed"
            await save_final_plan(trip_id, final_plan, status=status)
            await log_event(
                trip_id,
                "graph_done",
                payload={"status": status, "degraded_sections": final_plan.get("degraded_sections")},
            )
            yield {"event": "done", "status": status, "final_plan": final_plan}
        elif isinstance(final_plan, dict) and final_plan.get("failed"):
            msg = str(final_plan.get("error") or "Aggregator failed")
            await update_trip_status(trip_id, "failed", msg)
            await log_error(trip_id, msg, agent="graph")
            await log_event(trip_id, "graph_done", payload={"status": "failed", "message": msg})
            yield {"event": "error", "status": "failed", "message": msg}
        else:
            msg = "Graph finished without a final_plan"
            await update_trip_status(trip_id, "failed", msg)
            await log_error(trip_id, msg, agent="graph")
            await log_event(trip_id, "graph_done", payload={"status": "failed", "message": msg})
            yield {"event": "error", "status": "failed", "message": msg}
    except Exception as exc:
        logger.exception("planning graph failed for %s", trip_id)
        await update_trip_status(trip_id, "failed", str(exc))
        await log_error(
            trip_id,
            str(exc),
            agent="graph",
            details={"type": type(exc).__name__},
        )
        await log_event(trip_id, "graph_done", payload={"status": "failed", "message": str(exc)})
        yield {"event": "error", "status": "failed", "message": str(exc)}
