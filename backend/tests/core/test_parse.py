from unittest.mock import AsyncMock, patch

import pytest

from app.core.models import AggregatorPlanOutput, DestinationAgentOutput
from app.core.parse import parse_json_content, validate_with_repair


class TestParseJsonContent:
    def test_plain_json_object(self):
        assert parse_json_content('{"a": 1}') == {"a": 1}

    def test_fenced_json(self):
        text = '```json\n{"a": 1}\n```'
        assert parse_json_content(text) == {"a": 1}

    def test_fenced_without_language_tag(self):
        text = '```\n{"a": 1}\n```'
        assert parse_json_content(text) == {"a": 1}

    def test_object_embedded_in_prose(self):
        text = 'Sure, here is the plan: {"a": 1, "b": [1, 2]} hope that helps!'
        assert parse_json_content(text) == {"a": 1, "b": [1, 2]}

    def test_array_embedded_in_prose(self):
        text = "The options are: [1, 2, 3] -- take your pick"
        assert parse_json_content(text) == [1, 2, 3]

    def test_invalid_json_returns_none(self):
        assert parse_json_content("not json at all {") is None

    def test_empty_string_returns_none(self):
        assert parse_json_content("") is None
        assert parse_json_content("   ") is None

    def test_none_input_returns_none(self):
        assert parse_json_content(None) is None


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content


@pytest.mark.asyncio
class TestValidateWithRepair:
    async def test_valid_payload_needs_no_repair(self):
        payload = {
            "summary": "A trip",
            "budget_notes": "On budget",
            "tips": ["pack light"],
        }
        with patch("app.core.parse.invoke_llm", new=AsyncMock()) as mock_llm:
            model, degraded = await validate_with_repair(
                payload, "raw text", AggregatorPlanOutput, agent_name="test"
            )
        mock_llm.assert_not_called()
        assert degraded is False
        assert model.generation_status == "ok"
        assert model.summary == "A trip"

    async def test_repair_recovers_malformed_payload(self):
        bad_payload = {"summary": None, "budget_notes": None, "tips": None}
        fixed = _FakeResponse(
            '{"summary": "Fixed", "budget_notes": "Fixed notes", "tips": ["t1"]}'
        )
        with patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=fixed)) as mock_llm:
            model, degraded = await validate_with_repair(
                bad_payload, "raw text", AggregatorPlanOutput, agent_name="test"
            )
        mock_llm.assert_awaited_once()
        assert degraded is True
        assert model.generation_status == "ok"
        assert model.summary == "Fixed"

    async def test_repair_also_fails_degrades_to_unavailable(self):
        bad_payload = {"summary": None, "budget_notes": None, "tips": None}
        still_broken = _FakeResponse("not json at all")
        with patch(
            "app.core.parse.invoke_llm", new=AsyncMock(return_value=still_broken)
        ) as mock_llm:
            model, degraded = await validate_with_repair(
                bad_payload, "raw text", AggregatorPlanOutput, agent_name="test"
            )
        mock_llm.assert_awaited_once()
        assert degraded is True
        assert model.generation_status == "unavailable"
        # Explicit text, never a silent None.
        assert model.summary is not None
        assert "could not be generated" in model.summary
        assert model.tips and "could not be generated" in model.tips[0]

    async def test_repair_llm_call_raises_degrades_to_unavailable(self):
        bad_payload = {"summary": None, "budget_notes": None, "tips": None}
        with patch(
            "app.core.parse.invoke_llm", new=AsyncMock(side_effect=RuntimeError("groq down"))
        ):
            model, degraded = await validate_with_repair(
                bad_payload, "raw text", AggregatorPlanOutput, agent_name="test"
            )
        assert degraded is True
        assert model.generation_status == "unavailable"

    async def test_non_dict_payload_triggers_repair_path(self):
        fixed = _FakeResponse('{"summary": "ok", "budget_notes": "ok", "tips": []}')
        with patch("app.core.parse.invoke_llm", new=AsyncMock(return_value=fixed)) as mock_llm:
            model, degraded = await validate_with_repair(
                None, "not a json object", AggregatorPlanOutput, agent_name="test"
            )
        mock_llm.assert_awaited_once()
        assert degraded is True
        assert model.summary == "ok"

    async def test_destination_model_defaults_are_permissive(self):
        """A specialist-agent model (optional fields, defaults) should not
        need repair just because most fields are missing."""
        with patch("app.core.parse.invoke_llm", new=AsyncMock()) as mock_llm:
            model, degraded = await validate_with_repair(
                {}, "", DestinationAgentOutput, agent_name="destination"
            )
        mock_llm.assert_not_called()
        assert degraded is False
        assert model.attractions == []
        assert model.generation_status == "ok"
