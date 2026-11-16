from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.schemas import PreferencesUpdate, TripRequest, TripResponse, TripStatus


def _base_request(**overrides):
    payload = {
        "user_id": str(uuid4()),
        "destination": "Paris",
        "start_date": "2026-10-10",
        "end_date": "2026-10-12",
        "budget_usd": 1500.0,
    }
    payload.update(overrides)
    return payload


class TestTripRequest:
    def test_minimal_valid_request(self):
        req = TripRequest(**_base_request())
        assert req.destination == "Paris"
        assert req.currency == "USD"
        assert req.travellers == 1
        assert req.preferences == {}

    def test_rejects_invalid_start_date(self):
        with pytest.raises(ValidationError):
            TripRequest(**_base_request(start_date="not-a-date"))

    def test_rejects_invalid_end_date(self):
        with pytest.raises(ValidationError):
            TripRequest(**_base_request(end_date="12-10-2026"))

    def test_rejects_empty_destination(self):
        with pytest.raises(ValidationError):
            TripRequest(**_base_request(destination="   "))

    def test_destination_is_trimmed(self):
        req = TripRequest(**_base_request(destination="  Tokyo  "))
        assert req.destination == "Tokyo"

    def test_currency_normalized_to_uppercase(self):
        req = TripRequest(**_base_request(currency="inr"))
        assert req.currency == "INR"

    def test_rejects_non_alpha_currency(self):
        with pytest.raises(ValidationError):
            TripRequest(**_base_request(currency="1NR"))

    def test_rejects_wrong_length_currency(self):
        with pytest.raises(ValidationError):
            TripRequest(**_base_request(currency="DOLLAR"))

    def test_origin_trimmed_and_blank_becomes_none(self):
        req = TripRequest(**_base_request(origin="  Boston, MA  "))
        assert req.origin == "Boston, MA"
        req2 = TripRequest(**_base_request(origin="   "))
        assert req2.origin is None

    def test_rejects_negative_budget(self):
        with pytest.raises(ValidationError):
            TripRequest(**_base_request(budget_usd=-1))

    def test_zero_budget_allowed(self):
        req = TripRequest(**_base_request(budget_usd=0))
        assert req.budget_usd == 0

    @pytest.mark.parametrize("travellers", [0, 21])
    def test_travellers_out_of_range(self, travellers):
        with pytest.raises(ValidationError):
            TripRequest(**_base_request(travellers=travellers))

    @pytest.mark.parametrize("travellers", [1, 20])
    def test_travellers_boundary_values_allowed(self, travellers):
        req = TripRequest(**_base_request(travellers=travellers))
        assert req.travellers == travellers

    def test_rejects_missing_user_id(self):
        payload = _base_request()
        payload.pop("user_id")
        with pytest.raises(ValidationError):
            TripRequest(**payload)

    def test_preferences_default_and_passthrough(self):
        req = TripRequest(**_base_request(preferences={"pace": "slow"}))
        assert req.preferences == {"pace": "slow"}


class TestPreferencesUpdate:
    def test_requires_preferences_field(self):
        with pytest.raises(ValidationError):
            PreferencesUpdate()

    def test_accepts_arbitrary_dict(self):
        update = PreferencesUpdate(preferences={"lodging": "mid-range"})
        assert update.preferences == {"lodging": "mid-range"}


class TestTripResponse:
    def test_requires_trip_id_and_status(self):
        with pytest.raises(ValidationError):
            TripResponse(status="completed")

    def test_minimal_response(self):
        resp = TripResponse(trip_id="abc", status="partial")
        assert resp.status == "partial"
        assert resp.degraded_sections is None

    def test_degraded_sections_roundtrip(self):
        resp = TripResponse(
            trip_id="abc", status="partial", degraded_sections=["transport"]
        )
        assert resp.degraded_sections == ["transport"]


class TestTripStatus:
    def test_minimal(self):
        status = TripStatus(trip_id="abc", status="failed")
        assert status.error is None
