from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from app.state.travel_state import TravelState
from app.tools import maps_tool

llm = ChatOpenAI(model="gpt-4o")

ITINERARY_PROMPT = """
You are an expert travel itinerary planner.
Using this destination research: {destination_info}
Create a detailed itinerary based on: {user_request}
List out the daily plan.
"""

async def itinerary_planning_node(state: TravelState) -> TravelState:
    agent = create_react_agent(llm, tools=[maps_tool])
    result = await agent.ainvoke({"messages": [
        HumanMessage(content=ITINERARY_PROMPT.format(
            destination_info=state.get("destination_info", {}),
            user_request=state["user_request"]
        ))
    ]})
    state["itinerary"] = {"raw_output": result["messages"][-1].content}
    return state
