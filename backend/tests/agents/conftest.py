from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def mock_enrichment_network_calls(monkeypatch):
    """Specialist/aggregator nodes all funnel through app.agents.enrich,
    which calls Openverse (images) and the FX API (currency conversion) for
    cosmetic enrichment. Stub both with deterministic fakes so agent tests
    exercise their own logic without any real HTTP call.
    """
    monkeypatch.setattr(
        "app.agents.enrich.place_image_url", AsyncMock(return_value=None)
    )

    async def _identity_convert(amount, from_currency, to_currency):
        return round(float(amount), 2)

    monkeypatch.setattr(
        "app.agents.enrich.convert_amount", AsyncMock(side_effect=_identity_convert)
    )
