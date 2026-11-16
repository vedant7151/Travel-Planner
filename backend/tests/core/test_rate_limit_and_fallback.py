from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.llm import invoke_llm
from app.core.rate_limit import ProviderRateLimited, provider_call, retry_provider_call


@pytest.mark.asyncio
class TestProviderCall:
    async def test_calls_through_when_gate_allows(self):
        call = AsyncMock(return_value="ok")
        with patch("app.core.rate_limit.provider_rate_gate", new=AsyncMock(return_value=True)):
            result = await provider_call("groq", 10, 60, call)
        assert result == "ok"
        call.assert_awaited_once()

    async def test_raises_when_gate_denies(self):
        call = AsyncMock(return_value="ok")
        with patch("app.core.rate_limit.provider_rate_gate", new=AsyncMock(return_value=False)):
            with pytest.raises(ProviderRateLimited):
                await provider_call("groq", 10, 60, call)
        call.assert_not_called()


class TestRetryProviderCallPredicate:
    """retry_provider_call wraps tenacity around a should_retry() predicate
    that only fires on 429/5xx; everything else (network errors, 4xx) must
    not trigger the retry loop."""

    def _exc_with_status(self, status_code):
        exc = Exception("boom")
        exc.response = MagicMock(status_code=status_code)
        return exc

    @pytest.mark.asyncio
    async def test_retries_on_429(self):
        attempts = {"n": 0}

        @retry_provider_call()
        async def flaky():
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise self._exc_with_status(429)
            return "ok"

        result = await flaky()
        assert result == "ok"
        assert attempts["n"] == 2

    @pytest.mark.asyncio
    async def test_retries_on_5xx(self):
        attempts = {"n": 0}

        @retry_provider_call()
        async def flaky():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise self._exc_with_status(503)
            return "ok"

        result = await flaky()
        assert result == "ok"
        assert attempts["n"] == 3

    @pytest.mark.asyncio
    async def test_does_not_retry_on_400(self):
        attempts = {"n": 0}

        @retry_provider_call()
        async def flaky():
            attempts["n"] += 1
            raise self._exc_with_status(400)

        with pytest.raises(Exception):
            await flaky()
        assert attempts["n"] == 1

    @pytest.mark.asyncio
    async def test_does_not_retry_on_plain_exception_without_response(self):
        attempts = {"n": 0}

        @retry_provider_call()
        async def flaky():
            attempts["n"] += 1
            raise RuntimeError("no .response attribute at all")

        with pytest.raises(RuntimeError):
            await flaky()
        assert attempts["n"] == 1

    @pytest.mark.asyncio
    async def test_gives_up_after_three_attempts(self):
        attempts = {"n": 0}

        @retry_provider_call()
        async def always_429():
            attempts["n"] += 1
            raise self._exc_with_status(429)

        with pytest.raises(Exception):
            await always_429()
        assert attempts["n"] == 3


class _FakeResponse:
    def __init__(self, content):
        self.content = content


@pytest.mark.asyncio
class TestInvokeLlmGeminiFallback:
    async def test_uses_groq_when_configured_and_healthy(self):
        groq_response = _FakeResponse("groq says hi")
        with patch("app.core.llm.GROQ_API_KEY", "fake-groq-key"), \
             patch("app.core.llm.GEMINI_API_KEY", ""), \
             patch("app.core.llm._invoke_provider", new=AsyncMock(return_value=groq_response)) as mock_invoke:
            result = await invoke_llm([])

        assert result is groq_response
        mock_invoke.assert_awaited_once_with("groq", [])

    async def test_falls_back_to_gemini_when_groq_raises(self):
        gemini_response = _FakeResponse("gemini says hi")

        async def _side_effect(provider, messages):
            if provider == "groq":
                raise RuntimeError("groq rate limited")
            return gemini_response

        with patch("app.core.llm.GROQ_API_KEY", "fake-groq-key"), \
             patch("app.core.llm.GEMINI_API_KEY", "fake-gemini-key"), \
             patch("app.core.llm._invoke_provider", new=AsyncMock(side_effect=_side_effect)) as mock_invoke:
            result = await invoke_llm([])

        assert result is gemini_response
        assert mock_invoke.await_count == 2

    async def test_raises_when_both_providers_unavailable(self):
        async def _side_effect(provider, messages):
            raise RuntimeError(f"{provider} down")

        with patch("app.core.llm.GROQ_API_KEY", "fake-groq-key"), \
             patch("app.core.llm.GEMINI_API_KEY", "fake-gemini-key"), \
             patch("app.core.llm._invoke_provider", new=AsyncMock(side_effect=_side_effect)):
            with pytest.raises(RuntimeError) as exc_info:
                await invoke_llm([])

        assert "groq" in str(exc_info.value).lower() or "Groq" in str(exc_info.value)

    async def test_raises_immediately_when_neither_provider_configured(self):
        with patch("app.core.llm.GROQ_API_KEY", ""), patch("app.core.llm.GEMINI_API_KEY", ""):
            with pytest.raises(RuntimeError):
                await invoke_llm([])

    async def test_skips_gemini_when_not_configured_and_groq_fails(self):
        groq_failure = AsyncMock(side_effect=RuntimeError("groq down"))
        with patch("app.core.llm.GROQ_API_KEY", "fake-groq-key"), \
             patch("app.core.llm.GEMINI_API_KEY", ""), \
             patch("app.core.llm._invoke_provider", new=groq_failure) as mock_invoke:
            with pytest.raises(RuntimeError):
                await invoke_llm([])

        mock_invoke.assert_awaited_once_with("groq", [])
