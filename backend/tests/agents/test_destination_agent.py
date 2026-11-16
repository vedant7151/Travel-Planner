from unittest.mock import AsyncMock, patch

import pytest

from app.agents.destination import destination_research_node


def _state():
    return {
        "trip_id": "t1",
        "user_request": {
            "destination": "New York, NY",
            "origin": "Boston, MA",
            "start_date": "2026-10-10",
            "end_date": "2026-10-12",
        },
    }


class _FakeResponse:
    def __init__(self, content):
        self.content = content


@pytest.mark.asyncio
class TestDestinationAgent:
    async def test_well_formed_llm_output_passes_straight_through(self):
        parsed = {
            "attractions": ["Central Park"],
            "coordinates": {"lat": 40.71, "lon": -74.0},
            "nominatim_results": [{"display_name": "New York", "lat": 40.71, "lon": -74.0}],
            "weather": {"daily": {"temperature_2m_max": [20]}},
            "packing_tips": "Bring a light jacket",
            "notes": "Great walkable city",
            "visa_safety_cuisine": None,
            "tool_errors": [],
        }
        with patch(
            "app.agents.destination.run_react_json",
            new=AsyncMock(return_value=(parsed, '{"ok": true}', [], [])),
        ) as mock_react, patch("app.core.parse.invoke_llm", new=AsyncMock()) as mock_repair:
            result = await destination_research_node(_state())

        mock_react.assert_awaited_once()
        mock_repair.assert_not_called()  # valid payload needs no repair LLM call
        payload = result["destination_info"]
        assert payload["attractions"] == ["Central Park"]
        assert payload["generation_status"] == "ok"
        assert payload.get("failed") is not True
        assert result["errors"] == []

    async def test_tool_error_marks_failed_but_keeps_usable_payload(self):
        errors = ["places_tool: Nominatim request failed: timeout"]
        with patch(
            "app.agents.destination.run_react_json",
            new=AsyncMock(return_value=(None, "", errors, [])),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock()):
            result = await destination_research_node(_state())

        payload = result["destination_info"]
        assert payload["failed"] is True
        assert "Nominatim" in payload["error"]
        assert result["errors"] == errors

    async def test_wrong_shaped_json_triggers_repair_then_recovers(self):
        """Phase 6 path: the model returned JSON, but a field has the wrong
        shape (coordinates isn't a {lat, lon} object) -- schema validation
        fails and the repair LLM call fixes it."""
        raw = '{"coordinates": "somewhere", "attractions": "not a list"}'
        malformed = {"coordinates": "somewhere", "attractions": "not a list"}
        # The repair response must also correct the bad "coordinates" value
        # (validate_with_repair merges {**original, **repaired}, so a key
        # the repair response omits keeps its original, still-invalid value).
        fixed = _FakeResponse(
            '{"coordinates": null, "attractions": ["Central Park", "The Met"], "notes": "recovered"}'
        )
        with patch(
            "app.agents.destination.run_react_json",
            new=AsyncMock(return_value=(malformed, raw, [], [])),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=fixed)) as mock_repair:
            result = await destination_research_node(_state())

        mock_repair.assert_awaited_once()
        payload = result["destination_info"]
        assert payload["generation_status"] == "ok"
        assert payload["attractions"] == ["Central Park", "The Met"]
        assert payload["raw_text"] == raw

    async def test_repair_also_fails_degrades_explicitly(self):
        raw = '{"coordinates": "somewhere", "attractions": "not a list"}'
        malformed = {"coordinates": "somewhere", "attractions": "not a list"}
        still_broken = _FakeResponse("still not json")
        with patch(
            "app.agents.destination.run_react_json",
            new=AsyncMock(return_value=(malformed, raw, [], [])),
        ), patch(
            "app.core.parse.invoke_llm", new=AsyncMock(return_value=still_broken)
        ):
            result = await destination_research_node(_state())

        payload = result["destination_info"]
        assert payload["generation_status"] == "unavailable"
        assert payload["failed"] is True
        assert any("schema validation" in e for e in result["errors"])
        # Never a silent None -- an explicit "could not be generated" message.
        assert payload["notes"] is not None
        assert "could not be generated" in payload["notes"]

    async def test_fills_nominatim_results_from_tool_output_when_llm_omits_it(self):
        parsed = {"attractions": ["Central Park"]}
        tool_results = [
            {
                "name": "places_tool",
                "content": {"results": [{"display_name": "New York", "lat": 40.71, "lon": -74.0}]},
            }
        ]
        with patch(
            "app.agents.destination.run_react_json",
            new=AsyncMock(return_value=(parsed, "{}", [], tool_results)),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock()):
            result = await destination_research_node(_state())

        payload = result["destination_info"]
        assert len(payload["nominatim_results"]) == 1
        assert payload["nominatim_results"][0]["display_name"] == "New York"
