"""HTTP-layer tests using respx: these mock httpx itself (not the tool
functions), so they exercise the real app.tools.client.get_json path --
including retry_provider_call's 429/5xx retry logic -- without ever hitting
Nominatim, Open-Meteo, OSRM, Openverse, or the FX API for real.
"""
import httpx
import pytest
import respx

from app.tools.fx import convert_amount, fx_rates
from app.tools.maps import maps_tool
from app.tools.media import place_image_url
from app.tools.places import places_tool
from app.tools.weather import weather_tool


@pytest.mark.asyncio
class TestPlacesTool:
    async def test_successful_geocode(self):
        with respx.mock(assert_all_called=True) as mock:
            mock.get("https://nominatim.openstreetmap.org/search").mock(
                return_value=httpx.Response(
                    200,
                    json=[{"display_name": "New York, USA", "lat": "40.71", "lon": "-74.0", "type": "city"}],
                )
            )
            result = await places_tool.ainvoke({"query": "New York"})

        assert result["results"][0]["display_name"] == "New York, USA"
        assert "map_url" in result["results"][0]

    async def test_no_results_returns_explicit_error(self):
        with respx.mock(assert_all_called=True) as mock:
            mock.get("https://nominatim.openstreetmap.org/search").mock(
                return_value=httpx.Response(200, json=[])
            )
            result = await places_tool.ainvoke({"query": "Nowhereville"})

        assert result["error"] == "Nominatim returned no results"
        assert result["results"] == []

    async def test_upstream_500_surfaces_as_tool_error(self):
        with respx.mock(assert_all_called=True) as mock:
            mock.get("https://nominatim.openstreetmap.org/search").mock(
                return_value=httpx.Response(500)
            )
            result = await places_tool.ainvoke({"query": "Paris"})

        assert "error" in result
        assert result["results"] == []


@pytest.mark.asyncio
class TestWeatherTool:
    async def test_successful_forecast(self):
        with respx.mock(assert_all_called=True) as mock:
            mock.get("https://api.open-meteo.com/v1/forecast").mock(
                return_value=httpx.Response(200, json={"daily": {"temperature_2m_max": [20]}})
            )
            result = await weather_tool.ainvoke(
                {"lat": 40.71, "lon": -74.0, "start_date": "2026-10-10", "end_date": "2026-10-12"}
            )

        assert result["daily"]["temperature_2m_max"] == [20]

    async def test_out_of_range_dates_falls_back_to_near_term_forecast(self):
        with respx.mock(assert_all_called=True) as mock:
            out_of_range_params = {"start_date": "2099-01-01", "end_date": "2099-01-03"}
            mock.get("https://api.open-meteo.com/v1/forecast", params=out_of_range_params).mock(
                return_value=httpx.Response(400, json={"error": True, "reason": "date out of range"})
            )
            mock.get("https://api.open-meteo.com/v1/forecast").mock(
                return_value=httpx.Response(200, json={"daily": {"temperature_2m_max": [15]}})
            )
            result = await weather_tool.ainvoke(
                {"lat": 40.71, "lon": -74.0, "start_date": "2099-01-01", "end_date": "2099-01-03"}
            )

        assert result["daily"]["temperature_2m_max"] == [15]
        assert "note" in result


@pytest.mark.asyncio
class TestMapsTool:
    async def test_successful_route(self):
        with respx.mock(assert_all_called=True) as mock:
            mock.get(url__startswith="https://router.project-osrm.org/route/v1/driving/").mock(
                return_value=httpx.Response(
                    200, json={"code": "Ok", "routes": [{"duration": 1000, "distance": 5000}]}
                )
            )
            result = await maps_tool.ainvoke(
                {"start_lat": 42.36, "start_lon": -71.05, "end_lat": 40.71, "end_lon": -74.0}
            )

        assert result["code"] == "Ok"
        assert "map_url" in result

    async def test_osrm_error_code_surfaces(self):
        with respx.mock(assert_all_called=True) as mock:
            mock.get(url__startswith="https://router.project-osrm.org/route/v1/driving/").mock(
                return_value=httpx.Response(200, json={"code": "NoRoute", "message": "no route found"})
            )
            result = await maps_tool.ainvoke(
                {"start_lat": 42.36, "start_lon": -71.05, "end_lat": 40.71, "end_lon": -74.0}
            )

        assert "error" in result


@pytest.mark.asyncio
class TestFxTools:
    async def test_fx_rates_parses_and_uppercases(self):
        with respx.mock(assert_all_called=True) as mock:
            mock.get("https://open.er-api.com/v6/latest/USD").mock(
                return_value=httpx.Response(200, json={"result": "success", "rates": {"inr": 83.0, "eur": 0.9}})
            )
            rates = await fx_rates("usd")

        assert rates["INR"] == 83.0
        assert rates["USD"] == 1.0

    async def test_convert_amount_same_currency_short_circuits_without_http(self):
        with respx.mock(assert_all_called=False) as mock:
            # No route registered at all -- if the function tried to call
            # out, respx would raise. Same-currency conversion must not.
            result = await convert_amount(100.0, "USD", "usd")

        assert result == 100.0
        assert mock.calls.call_count == 0

    async def test_convert_amount_upstream_failure_returns_none(self):
        with respx.mock(assert_all_called=True) as mock:
            mock.get("https://open.er-api.com/v6/latest/USD").mock(
                return_value=httpx.Response(200, json={"result": "error", "error-type": "invalid-base"})
            )
            result = await convert_amount(100.0, "USD", "EUR")

        assert result is None


@pytest.mark.asyncio
class TestPlaceImageUrl:
    async def test_returns_first_result_url(self):
        with respx.mock(assert_all_called=True) as mock:
            mock.get("https://api.openverse.org/v1/images/").mock(
                return_value=httpx.Response(200, json={"results": [{"url": "https://img.example/a.jpg"}]})
            )
            url = await place_image_url("Eiffel Tower")

        assert url == "https://img.example/a.jpg"

    async def test_upstream_failure_returns_none_not_raises(self):
        with respx.mock(assert_all_called=True) as mock:
            mock.get("https://api.openverse.org/v1/images/").mock(
                return_value=httpx.Response(503)
            )
            url = await place_image_url("Eiffel Tower")

        assert url is None


@pytest.mark.asyncio
class TestRetryOnRateLimit:
    async def test_429_is_retried_then_succeeds(self):
        """Exercises retry_provider_call's real tenacity retry logic against
        an actual 429 response, proving the backoff path works without a
        real rate-limited API."""
        with respx.mock(assert_all_called=True) as mock:
            route = mock.get("https://nominatim.openstreetmap.org/search")
            route.side_effect = [
                httpx.Response(429),
                httpx.Response(200, json=[{"display_name": "Paris, France", "lat": "48.85", "lon": "2.35"}]),
            ]
            result = await places_tool.ainvoke({"query": "Paris"})

        assert route.call_count == 2
        assert result["results"][0]["display_name"] == "Paris, France"
