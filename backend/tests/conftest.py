"""Shared test fixtures.

Hard rule for this suite: no test may make a real network call. HTTP-bound
tools go through app.tools.client.get_json (a single httpx.AsyncClient),
which every test that touches it mocks with respx. LLM calls go through
app.core.llm.invoke_llm, which every agent/aggregator test monkeypatches
directly. The `block_network` autouse fixture below is a last-resort guard:
if anything slips through and tries a real socket connection, it fails fast
with a clear message instead of hanging or hitting a real rate-limited API.
"""
import socket

import pytest


class _BlockedNetworkCall(RuntimeError):
    pass


_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _is_loopback(address) -> bool:
    host = address[0] if isinstance(address, tuple) and address else address
    return isinstance(host, str) and host in _LOOPBACK_HOSTS


def _make_guard(real_fn):
    def _guard(self, address, *args, **kwargs):
        if _is_loopback(address):
            return real_fn(self, address, *args, **kwargs)
        raise _BlockedNetworkCall(
            f"A test attempted a real network connection to {address!r}. All "
            "external calls (Groq, Gemini, Nominatim, Open-Meteo, OSRM, DDG, "
            "Openverse, FX, Supabase) must be mocked in this suite. Only "
            "loopback connections (e.g. a local test Postgres) are allowed."
        )

    return _guard


@pytest.fixture(autouse=True)
def block_network(monkeypatch, request):
    """Fail fast on any non-loopback socket connection. Loopback stays open
    so DB tests can talk to a local disposable Postgres (see tests/db/).
    """
    if "allow_network" in request.keywords:
        yield
        return
    monkeypatch.setattr(socket.socket, "connect", _make_guard(socket.socket.connect))
    monkeypatch.setattr(socket.socket, "connect_ex", _make_guard(socket.socket.connect_ex))
    yield


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset module-level client/caches so tests don't leak state."""
    import app.core.llm as llm
    import app.core.redis as redis_mod
    import app.tools.client as http_client

    llm._llm = None
    llm._gemini = None
    redis_mod._client = None
    redis_mod._disabled = False
    http_client._client = None
    yield
    llm._llm = None
    llm._gemini = None
    redis_mod._client = None
    redis_mod._disabled = False
    http_client._client = None


@pytest.fixture(autouse=True)
def disable_redis(monkeypatch):
    """Force Redis off in every test, regardless of what's in the real
    environment: app.core.redis imports its config values by name (`from
    app.core.config import UPSTASH_...`), so patching app.core.config's
    attributes would not reach those already-bound names. Patching
    `_get_client` directly guarantees cache/rate-limit/lock calls fail open
    (as in prod when Upstash isn't configured) and never touch a real
    network endpoint, even if a real Upstash URL/token is configured.
    """
    import app.core.redis as redis_mod

    monkeypatch.setattr(redis_mod, "_get_client", lambda: None)
