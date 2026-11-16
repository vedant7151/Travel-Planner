from unittest.mock import AsyncMock, patch

import pytest

from app.agents.itinerary import itinerary_planning_node


def _state():
    return {
        "trip_id": "t1",
        "user_request": {
            "destination": "New York, NY",
            "origin": "Boston, MA",
            "start_date": "2026-10-10",
            "end_date": "2026-10-12",
        },
        "destination_info": {
            "coordinates": {"lat": 40.71, "lon": -74.0},
            "nominatim_results": [{"display_name": "New York", "lat": 40.71, "lon": -74.0}],
            "attractions": ["Central Park"],
        },
    }


class _FakeResponse:
    def __init__(self, content):
        self.content = content


@pytest.mark.asyncio
class TestItineraryAgent:
    async def test_well_formed_llm_output_passes_straight_through(self):
        parsed = {
            "days": [
                {"day": 1, "morning": "Central Park", "afternoon": "Met", "evening": "Dinner", "notes": None}
            ],
            "travel_legs": [],
            "warnings": [],
        }
        with patch(
            "app.agents.itinerary.run_react_json",
            new=AsyncMock(return_value=(parsed, '{"ok": true}', [], [])),
        ) as mock_react, patch("app.core.parse.invoke_llm", new=AsyncMock()) as mock_repair:
            result = await itinerary_planning_node(_state())

        mock_react.assert_awaited_once()
        mock_repair.assert_not_called()
        payload = result["itinerary"]
        assert len(payload["days"]) == 1
        assert payload["days"][0]["morning"] == "Central Park"
        assert payload["generation_status"] == "ok"
        assert result["errors"] == []

    async def test_missing_days_key_is_flagged_as_error(self):
        parsed = {"travel_legs": []}
        with patch(
            "app.agents.itinerary.run_react_json",
            new=AsyncMock(return_value=(parsed, "{}", [], [])),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock()):
            result = await itinerary_planning_node(_state())

        payload = result["itinerary"]
        assert payload["days"] == []
        assert payload["failed"] is True
        assert any("days missing" in e for e in result["errors"])

    async def test_wrong_shaped_days_triggers_repair_then_recovers(self):
        # itinerary.py normalizes a missing/non-list `days` to [] *before*
        # validation, so to exercise the repair path we need a field that
        # guard doesn't touch: travel_legs with the wrong shape.
        malformed = {"days": [{"day": 1}], "travel_legs": "not a list"}
        raw = '{"days": [{"day": 1}], "travel_legs": "not a list"}'
        fixed = _FakeResponse(
            '{"days": [{"day": 1, "morning": "Central Park"}], "travel_legs": []}'
        )
        with patch(
            "app.agents.itinerary.run_react_json",
            new=AsyncMock(return_value=(malformed, raw, [], [])),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=fixed)) as mock_repair:
            result = await itinerary_planning_node(_state())

        mock_repair.assert_awaited_once()
        payload = result["itinerary"]
        assert payload["generation_status"] == "ok"
        assert payload["days"][0]["morning"] == "Central Park"

    async def test_repair_also_fails_degrades_explicitly(self):
        malformed = {"days": [{"day": 1}], "travel_legs": "not a list"}
        raw = '{"days": [{"day": 1}], "travel_legs": "not a list"}'
        still_broken = _FakeResponse("still broken")
        with patch(
            "app.agents.itinerary.run_react_json",
            new=AsyncMock(return_value=(malformed, raw, [], [])),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=still_broken)):
            result = await itinerary_planning_node(_state())

        payload = result["itinerary"]
        assert payload["generation_status"] == "unavailable"
        assert payload["failed"] is True
        assert payload["warnings"]
        assert "could not be generated" in payload["warnings"][0]

    async def test_react_agent_crash_marks_failed(self):
        errors = ["itinerary: maps_tool failed: timeout"]
        with patch(
            "app.agents.itinerary.run_react_json",
            new=AsyncMock(return_value=(None, "", errors, [])),
        ), patch("app.core.parse.invoke_llm", new=AsyncMock()):
            result = await itinerary_planning_node(_state())

        payload = result["itinerary"]
        assert payload["failed"] is True
        assert errors[0] in result["errors"]
