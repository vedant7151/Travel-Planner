from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from app.state.travel_state import TravelState
from app.tools import flight_search_tool

llm = ChatOpenAI(model="gpt-4o")

TRANSPORT_PROMPT = """
Search transport options based on: {user_request}.
Return options sorted by price.
"""

async def transport_node(state: TravelState) -> TravelState:
    agent = create_react_agent(llm, tools=[flight_search_tool])
    result = await agent.ainvoke({"messages": [
        HumanMessage(content=TRANSPORT_PROMPT.format(user_request=state["user_request"]))
    ]})
    state["transport_options"] = [{"raw_output": result["messages"][-1].content}]
    return state
