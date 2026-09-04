import os

scaffold = {
    # PHASE 1
    ".env.example": '''OPENAI_API_KEY=
LANGSMITH_API_KEY=
LANGCHAIN_PROJECT=travel-planner
DB_URI=sqlite:///./travelplanner.db
''',
    
    # PHASE 2
    "backend/app/api/trips.py": '''from fastapi import APIRouter
from app.core.schemas import TripRequest, TripResponse

router = APIRouter()

@router.post("/plan", response_model=TripResponse)
async def plan_trip(request: TripRequest):
    return {"trip_id": "123", "status": "queued"}
''',
    
    "backend/app/api/ws.py": '''from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.websocket("/plan/{trip_id}")
async def plan_ws(websocket: WebSocket, trip_id: str):
    await websocket.accept()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
''',

    "backend/app/core/schemas.py": '''from pydantic import BaseModel
from typing import Optional, List

class TripRequest(BaseModel):
    user_id: str
    destination: str
    start_date: str
    end_date: str
    budget_usd: float
    travellers: int
    preferences: Optional[dict] = {}

class TripResponse(BaseModel):
    trip_id: str
    status: str
    itinerary: Optional[dict] = None
    accommodation: Optional[List[dict]] = None
    transport: Optional[List[dict]] = None
    total_estimated_cost: Optional[float] = None
''',
    
    # PHASE 3
    "backend/app/state/travel_state.py": '''from typing import TypedDict, Annotated, List, Optional
import operator

class TravelState(TypedDict):
    trip_id: str
    user_request: dict
    destination_info: Optional[dict]
    itinerary: Optional[dict]
    accommodation_options: Optional[List]
    transport_options: Optional[List]
    final_plan: Optional[dict]
    messages: Annotated[List, operator.add]
    errors: Annotated[List, operator.add]
    next_agent: Optional[str]
''',

    "backend/app/db/sqlite.py": '''import aiosqlite
import json

async def init_db(db_path: str = "./travelplanner.db"):
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                request JSON NOT NULL,
                final_plan JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.commit()
''',

    # PHASE 4
    "backend/app/agents/graph.py": '''from langgraph.graph import StateGraph, END
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
''',

    "backend/app/agents/supervisor.py": '''from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.state.travel_state import TravelState

SUPERVISOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a Travel Supervisor. Output the next agent to route to."),
    ("human", "State: {state_summary}"),
])

llm = ChatOpenAI(model="gpt-4o")

async def supervisor_node(state: TravelState) -> TravelState:
    # Stubbed
    state["next_agent"] = "end"
    return state
''',

    "backend/app/__init__.py": "",
    "backend/app/api/__init__.py": "",
    "backend/app/core/__init__.py": "",
    "backend/app/state/__init__.py": "",
    "backend/app/db/__init__.py": "",
    "backend/app/agents/__init__.py": ""
}

for filepath, content in scaffold.items():
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

print("Scaffold generation complete.")
