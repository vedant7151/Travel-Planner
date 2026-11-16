from unittest.mock import AsyncMock, patch

import pytest

from app.agents.accommodation import accommodation_node


def _state():
    return {
        "trip_id": "t1",
        "user_request": {
            "destination": "New York, NY",
            "travellers": 2,
            "start_date": "2026-10-10",
            "end_date": "2026-10-12",
            "budget_usd": 1500.0,
            "currency": "USD",
        },
        "destination_info": {"map_url": "https://osm.example/x", "image_url": None},
    }


class _FakeResponse:
    def __init__(self, content):
        self.content = content


@pytest.mark.asyncio
class TestAccommodationAgent:
    async def test_well_formed_llm_output_becomes_options(self):
        parsed = {
            "options": [
                {"title": "Hotel A", "snippet": "$130/night", "href": "https://a", "stated_price_or_null": "$130"}
            ],
            "warnings": [],
        }
        with patch(
            "app.agents.accommodation.run_react_json",
            new=AsyncMock(return_value=(parsed, "{}", [], [])),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock()) as mock_repair:
            result = await accommodation_node(_state())

        mock_repair.assert_not_called()
        options = result["accommodation_options"]
        assert options[0]["title"] == "Hotel A"
        assert result["errors"] == []

    async def test_no_results_falls_back_to_failed_marker(self):
        # parsed=None (not a dict) always needs a repair attempt; make the
        # repair fail too so there are truly no options/listings/raw text.
        still_broken = _FakeResponse("still not json")
        with patch(
            "app.agents.accommodation.run_react_json",
            new=AsyncMock(return_value=(None, "", [], [])),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=still_broken)):
            result = await accommodation_node(_state())

        options = result["accommodation_options"]
        assert len(options) == 1
        assert options[0]["failed"] is True

    async def test_duckduckgo_listings_used_when_llm_returns_no_options(self):
        tool_results = [
            {
                "name": "hotel_search_tool",
                "content": {
                    "results": [
                        {"title": "Hotel B", "body": "cheap stay", "href": "https://b"}
                    ]
                },
            }
        ]
        with patch(
            "app.agents.accommodation.run_react_json",
            new=AsyncMock(return_value=(None, "", [], tool_results)),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock()):
            result = await accommodation_node(_state())

        options = result["accommodation_options"]
        assert options[0]["title"] == "Hotel B"

    async def test_wrong_shaped_options_triggers_repair_then_recovers(self):
        malformed = {"options": "not a list", "warnings": []}
        raw = '{"options": "not a list"}'
        fixed = _FakeResponse(
            '{"options": [{"title": "Hotel C", "snippet": "ok"}], "warnings": []}'
        )
        with patch(
            "app.agents.accommodation.run_react_json",
            new=AsyncMock(return_value=(malformed, raw, [], [])),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=fixed)) as mock_repair:
            result = await accommodation_node(_state())

        mock_repair.assert_awaited_once()
        options = result["accommodation_options"]
        assert options[0]["title"] == "Hotel C"

    async def test_repair_also_fails_echoes_raw_text_as_last_resort(self):
        """When options/listings are both empty but raw text exists, the
        agent's pre-existing last-resort fallback echoes the raw text rather
        than inventing content -- this predates and is unrelated to Phase 6
        schema validation, which still correctly flags the error."""
        malformed = {"options": "not a list", "warnings": []}
        raw = '{"options": "not a list"}'
        still_broken = _FakeResponse("still broken")
        with patch(
            "app.agents.accommodation.run_react_json",
            new=AsyncMock(return_value=(malformed, raw, [], [])),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=still_broken)):
            result = await accommodation_node(_state())

        options = result["accommodation_options"]
        assert options[0]["text"] == raw
        assert any("schema validation" in e for e in result["errors"])

    async def test_repair_also_fails_and_no_raw_text_degrades_to_failed_marker(self):
        malformed = {"options": "not a list", "warnings": []}
        still_broken = _FakeResponse("still broken")
        with patch(
            "app.agents.accommodation.run_react_json",
            new=AsyncMock(return_value=(malformed, "", [], [])),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=still_broken)):
            result = await accommodation_node(_state())

        options = result["accommodation_options"]
        assert options[0]["failed"] is True
        assert any("schema validation" in e for e in result["errors"])
