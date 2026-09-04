from langgraph.graph import StateGraph, END
from app.state.travel_state import TravelState
from app.agents.supervisor import supervisor_node

def stub_node(state: TravelState) -> TravelState:
    return state

def route_to_agents(state: TravelState) -> str:
    return state.get("next_agent", "end")

def build_graph():
    g = StateGraph(TravelState)
    g.add_node("supervisor", supervisor_node)
    g.add_node("destination", stub_node)
    g.add_node("itinerary", stub_node)
    g.add_node("accommodation", stub_node)
    g.add_node("transport", stub_node)
    g.add_node("aggregator", stub_node)

    g.set_entry_point("supervisor")

    g.add_conditional_edges("supervisor", route_to_agents, {
        "destination": "destination",
        "itinerary": "itinerary",
        "accommodation": "accommodation",
        "transport": "transport",
        "aggregate": "aggregator",
        "end": END,
    })

    for node in ["destination", "itinerary", "accommodation", "transport"]:
        g.add_edge(node, "supervisor")

    g.add_edge("aggregator", END)
    return g.compile()
