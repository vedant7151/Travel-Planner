from collections.abc import Sequence
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from app.core.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_RATE_LIMIT,
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_RATE_LIMIT,
)
from app.core.rate_limit import ProviderRateLimited, provider_call, retry_provider_call

_llm: ChatGroq | None = None
_gemini: ChatGoogleGenerativeAI | None = None


def get_llm() -> ChatGroq:
    global _llm
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add a free Groq key."
        )
    if _llm is None:
        _llm = ChatGroq(
            model=GROQ_MODEL,
            temperature=0,
            api_key=GROQ_API_KEY,
            max_retries=0,
        )
    return _llm


def get_gemini() -> ChatGoogleGenerativeAI:
    global _gemini
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    if _gemini is None:
        _gemini = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            temperature=0,
            google_api_key=GEMINI_API_KEY,
            max_retries=0,
        )
    return _gemini


@retry_provider_call()
async def _invoke_provider(provider: str, messages: Sequence[BaseMessage]) -> Any:
    estimated_tokens = max(1, sum(len(str(message.content)) for message in messages) // 4)
    if provider == "groq":
        model = get_llm()
        limit = GROQ_RATE_LIMIT
        call = lambda: model.ainvoke(messages)
        units = estimated_tokens
    else:
        model = get_gemini()
        limit = GEMINI_RATE_LIMIT
        call = lambda: model.ainvoke(messages)
        units = 1
    return await provider_call(provider, limit, 60, call, units=units)


async def invoke_llm(messages: Sequence[BaseMessage]) -> Any:
    if GROQ_API_KEY:
        try:
            return await _invoke_provider("groq", messages)
        except ProviderRateLimited as exc:
            groq_error = exc
        except Exception as exc:
            groq_error = exc
    else:
        groq_error = RuntimeError("GROQ_API_KEY is not configured")

    if GEMINI_API_KEY:
        try:
            return await _invoke_provider("gemini", messages)
        except Exception as exc:
            raise RuntimeError(f"Groq unavailable ({groq_error}); Gemini unavailable ({exc})") from exc
    raise RuntimeError(f"Groq unavailable and Gemini is not configured: {groq_error}") from groq_error


async def get_agent_model():
    if GROQ_API_KEY:
        try:
            allowed = await provider_call(
                "groq", GROQ_RATE_LIMIT, 60, lambda: _true()
            )
            if allowed:
                return get_llm(), "groq"
        except Exception:
            pass
    if GEMINI_API_KEY:
        allowed = await provider_call(
            "gemini", GEMINI_RATE_LIMIT, 60, lambda: _true()
        )
        if allowed:
            return get_gemini(), "gemini"
    raise ProviderRateLimited("All configured LLM provider limits are exhausted")


async def _true() -> bool:
    return True


async def close_llm() -> None:
    global _llm, _gemini
    if _llm is None and _gemini is None:
        return
    for model in (_llm, _gemini):
        if model is None:
            continue
        for attr in ("async_client", "client"):
            client = getattr(model, attr, None)
            close = getattr(client, "aclose", None) or getattr(client, "close", None)
            if close is not None:
                result = close()
                if hasattr(result, "__await__"):
                    await result
    _llm = None
    _gemini = None
