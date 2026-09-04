from langchain_openai import ChatOpenAI
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
