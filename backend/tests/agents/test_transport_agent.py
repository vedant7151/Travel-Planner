from unittest.mock import AsyncMock, patch

import pytest

from app.agents.transport import transport_node


def _state():
    return {
        "trip_id": "t1",
        "user_request": {
            "destination": "New York, NY",
            "origin": "Boston, MA",
            "travellers": 2,
            "start_date": "2026-10-10",
            "end_date": "2026-10-12",
            "currency": "USD",
        },
        "destination_info": {"map_url": "https://osm.example/x", "image_url": None},
    }


class _FakeResponse:
    def __init__(self, content):
        self.content = content


@pytest.mark.asyncio
class TestTransportAgent:
    async def test_well_formed_llm_output_becomes_options(self):
        parsed = {
            "options": [
                {"title": "Flight A", "snippet": "$80", "href": "https://a", "mode_if_stated": "flight"}
            ],
            "query_used": "flights Boston to New York",
            "warnings": [],
        }
        with patch(
            "app.agents.transport.run_react_json",
            new=AsyncMock(return_value=(parsed, "{}", [], [])),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock()) as mock_repair:
            result = await transport_node(_state())

        mock_repair.assert_not_called()
        options = result["transport_options"]
        assert options[0]["title"] == "Flight A"
        assert result["errors"] == []

    async def test_rate_limit_error_from_react_agent_marks_failed(self):
        """Mirrors the exact scenario in output.txt: the transport LLM call
        hit a 429 inside run_react_json, which already reports it as an
        error and returns no parsed JSON."""
        errors = [
            "transport failed: Error code: 429 - rate_limit_exceeded"
        ]
        with patch(
            "app.agents.transport.run_react_json",
            new=AsyncMock(return_value=(None, "", errors, [])),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=_FakeResponse("still broken"))):
            result = await transport_node(_state())

        options = result["transport_options"]
        assert options[0]["failed"] is True
        assert errors[0] in result["errors"]

    async def test_duckduckgo_listings_used_when_llm_returns_no_options(self):
        tool_results = [
            {
                "name": "flight_search_tool",
                "content": {
                    "results": [
                        {"title": "Flight B", "body": "nonstop", "href": "https://b"}
                    ]
                },
            }
        ]
        with patch(
            "app.agents.transport.run_react_json",
            new=AsyncMock(return_value=(None, "", [], tool_results)),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=_FakeResponse("still broken"))):
            result = await transport_node(_state())

        options = result["transport_options"]
        assert options[0]["title"] == "Flight B"
        assert options[0]["source"] == "duckduckgo"

    async def test_wrong_shaped_options_triggers_repair_then_recovers(self):
        malformed = {"options": "not a list", "warnings": []}
        raw = '{"options": "not a list"}'
        fixed = _FakeResponse(
            '{"options": [{"title": "Flight C", "mode_if_stated": "train"}], "warnings": []}'
        )
        with patch(
            "app.agents.transport.run_react_json",
            new=AsyncMock(return_value=(malformed, raw, [], [])),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=fixed)) as mock_repair:
            result = await transport_node(_state())

        mock_repair.assert_awaited_once()
        options = result["transport_options"]
        assert options[0]["title"] == "Flight C"

    async def test_repair_also_fails_and_no_raw_text_degrades_to_failed_marker(self):
        malformed = {"options": "not a list", "warnings": []}
        still_broken = _FakeResponse("still broken")
        with patch(
            "app.agents.transport.run_react_json",
            new=AsyncMock(return_value=(malformed, "", [], [])),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=still_broken)):
            result = await transport_node(_state())

        options = result["transport_options"]
        assert options[0]["failed"] is True
        assert any("schema validation" in e for e in result["errors"])
