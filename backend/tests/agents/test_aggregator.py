from unittest.mock import AsyncMock, patch

import pytest

from app.agents import aggregator as agg


def _state(**overrides):
    base = {
        "trip_id": None,  # None skips DB persistence in these unit tests
        "user_request": {"destination": "New York, NY", "origin": "Boston, MA"},
        "destination_info": {"notes": "nice city"},
        "itinerary": {"days": [{"day": 1}]},
        "accommodation_options": [{"title": "Hotel A"}],
        "transport_options": [{"title": "Flight A"}],
        "errors": [],
    }
    base.update(overrides)
    return base


class _FakeResponse:
    def __init__(self, content):
        self.content = content


@pytest.mark.asyncio
class TestAggregatorNode:
    async def test_well_formed_plan_is_completed(self):
        good = _FakeResponse(
            '{"summary": "3-day NY trip.", "budget_notes": "Within budget.", '
            '"tips": ["Pack layers"], "itinerary": {"days": [{"day": 1}]}, '
            '"accommodation": [{"title": "Hotel A"}], "transport": [{"title": "Flight A"}], '
            '"warnings": []}'
        )
        with patch("app.agents.aggregator.invoke_llm", new=AsyncMock(return_value=good)):
            result = await agg.aggregator_node(_state())

        fp = result["final_plan"]
        assert fp["status"] == "completed"
        assert fp["degraded_sections"] == []
        assert fp["validation_status"] == "ok"
        assert fp["text"] is None  # no raw-text leak once parsing succeeded
        assert fp["structured"]["summary"] == "3-day NY trip."
        assert fp["structured"]["tips"] == ["Pack layers"]

    async def test_transport_failure_yields_partial_status(self):
        """Regression test for the exact output.txt scenario: transport hit
        a 429 and returned a failed marker, but destination/itinerary/
        accommodation succeeded -- the trip must save as partial, not
        completed, with summary/tips/budget_notes still populated."""
        good = _FakeResponse(
            '{"summary": "3-day NY trip.", "budget_notes": "Within budget.", '
            '"tips": ["Pack layers"], "itinerary": {"days": [{"day": 1}]}, '
            '"accommodation": [{"title": "Hotel A"}], "transport": [], '
            '"warnings": ["transport failed: rate limit"]}'
        )
        state = _state(
            transport_options=[{"failed": True, "error": "transport failed: 429 rate_limit_exceeded"}],
            errors=["transport: transport failed: 429 rate_limit_exceeded"],
        )
        with patch("app.agents.aggregator.invoke_llm", new=AsyncMock(return_value=good)):
            result = await agg.aggregator_node(state)

        fp = result["final_plan"]
        assert fp["status"] == "partial"
        assert fp["degraded_sections"] == ["transport"]
        assert fp["structured"]["summary"] == "3-day NY trip."
        # Enriched with map_url/image_url by finalize_plan_media_and_prices,
        # but the real title from state must survive (passthrough/merge).
        assert fp["structured"]["accommodation"][0]["title"] == "Hotel A"

    async def test_malformed_llm_output_retries_then_degrades_explicitly(self):
        broken = _FakeResponse("not json at all, still broken")
        with patch("app.agents.aggregator.invoke_llm", new=AsyncMock(return_value=broken)), \
             patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=broken)):
            result = await agg.aggregator_node(_state())

        fp = result["final_plan"]
        assert fp["validation_status"] == "unavailable"
        assert fp["text"] is not None  # raw text kept for debugging on full failure
        assert "could not be generated" in fp["structured"]["summary"]
        assert "could not be generated" in fp["structured"]["budget_notes"]
        # Passthrough state is preserved even though the aggregator itself failed.
        assert fp["structured"]["accommodation"][0]["title"] == "Hotel A"

    async def test_malformed_output_recovered_by_repair(self):
        broken = _FakeResponse("not json at all")
        fixed = _FakeResponse(
            '{"summary": "Recovered summary", "budget_notes": "Recovered notes", "tips": []}'
        )
        with patch("app.agents.aggregator.invoke_llm", new=AsyncMock(return_value=broken)), \
             patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=fixed)):
            result = await agg.aggregator_node(_state())

        fp = result["final_plan"]
        assert fp["validation_status"] == "ok"
        assert fp["text"] is None
        assert fp["structured"]["summary"] == "Recovered summary"

    async def test_llm_invocation_exception_degrades_to_unavailable(self):
        with patch(
            "app.agents.aggregator.invoke_llm", new=AsyncMock(side_effect=RuntimeError("groq down"))
        ):
            result = await agg.aggregator_node(_state())

        fp = result["final_plan"]
        assert fp["validation_status"] == "unavailable"
        assert "could not be generated" in fp["structured"]["summary"]

    async def test_all_sections_degraded_is_failed(self):
        broken = _FakeResponse("garbled")
        state = _state(
            destination_info={"failed": True, "error": "destination failed"},
            itinerary={"failed": True, "error": "itinerary failed"},
            accommodation_options=[{"failed": True, "error": "acc failed"}],
            transport_options=[{"failed": True, "error": "transport failed"}],
            errors=["destination: failed", "itinerary: failed", "accommodation: failed", "transport: failed"],
        )
        with patch("app.agents.aggregator.invoke_llm", new=AsyncMock(return_value=broken)), \
             patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=broken)):
            result = await agg.aggregator_node(state)

        fp = result["final_plan"]
        assert fp["status"] == "failed"
        assert set(fp["degraded_sections"]) == {
            "destination", "itinerary", "accommodation", "transport", "aggregator"
        }
