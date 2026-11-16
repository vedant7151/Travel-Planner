from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.core.llm import get_agent_model, retry_provider_call
from app.core.logging import logger
from app.core.parse import parse_json_content

JSON_ONLY = (
    "\n\nRespond with a single JSON object only. "
    "Use null for unknown fields. Do not invent hotels, flights, prices, "
    "attractions, or facts that did not come from a tool result."
)


@retry_provider_call()
async def _invoke_agent(agent, prompt: str):
    return await agent.ainvoke(
        {"messages": [HumanMessage(content=prompt)]},
        {"recursion_limit": 12},
    )


def message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _parse_tool_body(raw: str) -> Any:
    parsed = parse_json_content(raw)
    return parsed if parsed is not None else raw


def collect_tool_results(messages: list) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        body = _parse_tool_body(message_text(msg.content))
        results.append({"name": getattr(msg, "name", None), "content": body})
    return results


def ddg_listings(tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map DuckDuckGo tool payloads to listing dicts. Does not invent prices."""
    listings: list[dict[str, Any]] = []
    for item in tool_results:
        payload = item.get("content")
        if not isinstance(payload, dict):
            continue
        rows = payload.get("results")
        if not isinstance(rows, list):
            continue
        if payload.get("error"):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            listings.append(
                {
                    "title": row.get("title"),
                    "snippet": row.get("body") or row.get("snippet"),
                    "href": row.get("href"),
                    "stated_price_or_null": None,
                    "source": "duckduckgo",
                }
            )
    return listings


def tool_errors(tool_results: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for item in tool_results:
        payload = item.get("content")
        name = item.get("name") or "tool"
        if isinstance(payload, dict) and payload.get("error"):
            errors.append(f"{name}: {payload['error']}")
    return errors


async def run_react_json(
    prompt: str,
    tools: list,
    *,
    agent_name: str = "specialist",
    trip_id: str | None = None,
) -> tuple[Any, str, list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    try:
        llm, _provider = await get_agent_model()
        agent = create_agent(llm, tools=tools, system_prompt=JSON_ONLY.strip())
        result = await _invoke_agent(agent, prompt)
    except Exception as exc:
        logger.exception(
            "%s react agent failed",
            agent_name,
            extra={"agent": agent_name, "trip_id": trip_id},
        )
        return None, "", [f"{agent_name} failed: {exc}"], []

    messages = result.get("messages") or []
    tool_results = collect_tool_results(messages)
    errors.extend(tool_errors(tool_results))

    last_ai = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            last_ai = message_text(msg.content)
            if last_ai.strip():
                break

    parsed = parse_json_content(last_ai) if last_ai else None
    if parsed is None:
        errors.append(f"{agent_name}: model output was not valid JSON; stored as text only.")
        parsed = {"text": last_ai} if last_ai else None
    return parsed, last_ai, errors, tool_results
