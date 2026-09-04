from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from app.state.travel_state import TravelState
from app.tools import hotel_search_tool

llm = ChatOpenAI(model="gpt-4o")

ACCOMMODATION_PROMPT = """
Search for accommodation based on this request: {user_request}.
Return the top 5 options.
"""

async def accommodation_node(state: TravelState) -> TravelState:
    agent = create_react_agent(llm, tools=[hotel_search_tool])
    result = await agent.ainvoke({"messages": [
        HumanMessage(content=ACCOMMODATION_PROMPT.format(user_request=state["user_request"]))
    ]})
    state["accommodation_options"] = [{"raw_output": result["messages"][-1].content}]
    return state
