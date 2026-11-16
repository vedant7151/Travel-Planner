from unittest.mock import AsyncMock, patch

import pytest

from app.agents.supervisor import (
    _parse_token,
    fallback_route,
    is_legal_route,
    route_to_agents,
    supervisor_node,
)


def _state(**overrides):
    base = {
        "trip_id": "t1",
        "user_request": {"destination": "Paris"},
        "destination_info": None,
        "itinerary": None,
        "accommodation_options": None,
        "transport_options": None,
        "final_plan": None,
        "errors": [],
    }
    base.update(overrides)
    return base


class TestFallbackRoute:
    def test_routes_to_destination_first(self):
        assert fallback_route(_state()) == "destination"

    def test_routes_to_itinerary_once_destination_present(self):
        state = _state(destination_info={"notes": "ok"})
        assert fallback_route(state) == "itinerary"

    def test_routes_to_accommodation_once_itinerary_present(self):
        state = _state(destination_info={"notes": "ok"}, itinerary={"days": []})
        assert fallback_route(state) == "accommodation"

    def test_routes_to_transport_once_accommodation_present(self):
        state = _state(
            destination_info={"notes": "ok"},
            itinerary={"days": []},
            accommodation_options=[{"title": "Hotel"}],
        )
        assert fallback_route(state) == "transport"

    def test_routes_to_aggregate_once_all_specialists_present(self):
        state = _state(
            destination_info={"notes": "ok"},
            itinerary={"days": []},
            accommodation_options=[{"title": "Hotel"}],
            transport_options=[{"title": "Flight"}],
        )
        assert fallback_route(state) == "aggregate"

    def test_routes_to_end_once_final_plan_present(self):
        state = _state(
            destination_info={"notes": "ok"},
            itinerary={"days": []},
            accommodation_options=[{"title": "Hotel"}],
            transport_options=[{"title": "Flight"}],
            final_plan={"structured": {}},
        )
        assert fallback_route(state) == "end"

    def test_failed_specialist_still_counts_as_filled(self):
        """A specialist that returned a failure marker has still 'run' --
        the supervisor should move on rather than loop forever."""
        state = _state(destination_info={"failed": True, "error": "boom"})
        assert fallback_route(state) == "itinerary"

    def test_failed_list_specialist_counts_as_filled(self):
        state = _state(
            destination_info={"notes": "ok"},
            itinerary={"days": []},
            accommodation_options=[{"failed": True, "error": "boom"}],
        )
        assert fallback_route(state) == "transport"

    def test_empty_dict_does_not_count_as_filled(self):
        state = _state(destination_info={})
        assert fallback_route(state) == "destination"

    def test_empty_list_does_not_count_as_filled(self):
        state = _state(destination_info={"notes": "ok"}, itinerary={"days": []}, accommodation_options=[])
        assert fallback_route(state) == "accommodation"


class TestIsLegalRoute:
    def test_unknown_choice_is_illegal(self):
        assert is_legal_route(_state(), "not_a_real_agent") is False

    def test_destination_legal_when_missing(self):
        assert is_legal_route(_state(), "destination") is True

    def test_destination_illegal_once_present(self):
        state = _state(destination_info={"notes": "ok"})
        assert is_legal_route(state, "destination") is False

    def test_itinerary_illegal_before_destination(self):
        assert is_legal_route(_state(), "itinerary") is False

    def test_itinerary_legal_after_destination(self):
        state = _state(destination_info={"notes": "ok"})
        assert is_legal_route(state, "itinerary") is True

    def test_accommodation_requires_destination_only(self):
        state = _state(destination_info={"notes": "ok"})
        assert is_legal_route(state, "accommodation") is True

    def test_accommodation_illegal_once_present(self):
        state = _state(destination_info={"notes": "ok"}, accommodation_options=[{"title": "H"}])
        assert is_legal_route(state, "accommodation") is False

    def test_transport_requires_destination_only(self):
        state = _state(destination_info={"notes": "ok"})
        assert is_legal_route(state, "transport") is True

    def test_aggregate_illegal_until_every_specialist_done(self):
        state = _state(destination_info={"notes": "ok"})
        assert is_legal_route(state, "aggregate") is False

    def test_aggregate_legal_once_all_specialists_done(self):
        state = _state(
            destination_info={"notes": "ok"},
            itinerary={"days": []},
            accommodation_options=[{"title": "Hotel"}],
            transport_options=[{"title": "Flight"}],
        )
        assert is_legal_route(state, "aggregate") is True

    def test_end_illegal_without_final_plan(self):
        assert is_legal_route(_state(), "end") is False

    def test_end_legal_with_final_plan(self):
        state = _state(
            destination_info={"notes": "ok"},
            itinerary={"days": []},
            accommodation_options=[{"title": "Hotel"}],
            transport_options=[{"title": "Flight"}],
            final_plan={"structured": {}},
        )
        assert is_legal_route(state, "end") is True


class TestParseToken:
    @pytest.mark.parametrize("raw,expected", [
        ("destination", "destination"),
        ("  Destination  ", "destination"),
        ("'itinerary'", "itinerary"),
        ('"accommodation"', "accommodation"),
        ("aggregator", "aggregate"),
        ("hotel", "accommodation"),
        ("flight", "transport"),
        ("end", "end"),
        ("", ""),
        ("   ", ""),
    ])
    def test_token_normalization(self, raw, expected):
        assert _parse_token(raw) == expected


class TestRouteToAgents:
    def test_uses_next_agent_when_legal(self):
        state = _state(next_agent="destination")
        assert route_to_agents(state) == "destination"

    def test_falls_back_when_next_agent_illegal(self):
        state = _state(destination_info={"notes": "ok"}, next_agent="destination")
        assert route_to_agents(state) == "itinerary"

    def test_falls_back_when_next_agent_missing(self):
        state = _state()
        assert route_to_agents(state) == "destination"


class _FakeResponse:
    def __init__(self, content):
        self.content = content


@pytest.mark.asyncio
class TestSupervisorNode:
    async def test_uses_llm_token_when_legal(self):
        state = _state(destination_info={"notes": "ok"})
        with patch(
            "app.agents.supervisor.invoke_llm",
            new=AsyncMock(return_value=_FakeResponse("itinerary")),
        ):
            result = await supervisor_node(state)
        assert result == {"next_agent": "itinerary"}

    async def test_ignores_illegal_llm_token_and_uses_fallback(self):
        state = _state()  # destination_info missing -> only "destination" is legal
        with patch(
            "app.agents.supervisor.invoke_llm",
            new=AsyncMock(return_value=_FakeResponse("aggregate")),
        ):
            result = await supervisor_node(state)
        assert result == {"next_agent": "destination"}

    async def test_llm_failure_uses_fallback_route(self):
        state = _state()
        with patch(
            "app.agents.supervisor.invoke_llm",
            new=AsyncMock(side_effect=RuntimeError("groq down")),
        ):
            result = await supervisor_node(state)
        assert result == {"next_agent": "destination"}
