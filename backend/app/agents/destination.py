from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from app.state.travel_state import TravelState
from app.tools import weather_tool, places_tool

llm = ChatOpenAI(model="gpt-4o")

DESTINATION_PROMPT = """
You are a destination research expert. Given: {user_request}, provide:
1. Top attractions and experiences
2. Weather and packing tips for the travel period
Use the available tools to fetch live data.
"""

async def destination_research_node(state: TravelState) -> TravelState:
    agent = create_react_agent(llm, tools=[places_tool, weather_tool])
    result = await agent.ainvoke({
        "messages": [HumanMessage(content=DESTINATION_PROMPT.format(user_request=state["user_request"]))]
    })
    state["destination_info"] = {"raw_output": result["messages"][-1].content}
    return state
