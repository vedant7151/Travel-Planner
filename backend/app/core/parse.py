import json
import re
from typing import Any, TypeVar

from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from app.core.llm import invoke_llm
from app.core.logging import logger
from app.core.models import LLMOutputModel

T = TypeVar("T", bound=LLMOutputModel)

REPAIR_PROMPT = """You produced output that failed schema validation.

Original output:
{raw}

Validation error:
{error}

Required JSON schema:
{schema}

Return ONLY a corrected JSON object that satisfies this schema. Use null or empty
arrays for fields you cannot determine. No markdown, no commentary, no code fences.
"""


def parse_json_content(text: str) -> Any:
    """Parse JSON from an LLM reply. Returns None if nothing valid is found."""
    if not text or not str(text).strip():
        return None
    raw = str(text).strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fenced:
        raw = fenced.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
    return None


async def validate_with_repair(
    payload: Any,
    raw_text: str,
    model_cls: type[T],
    *,
    agent_name: str,
) -> tuple[T, bool]:
    """Validate payload against model_cls. Retries once via an LLM repair prompt on
    failure, then falls back to an explicit model_cls.unavailable() state.

    Returns (validated_model, degraded) where degraded is True if a repair was
    needed or the fallback was used.
    """
    try:
        if not isinstance(payload, dict):
            raise ValueError("model output was not a JSON object")
        return model_cls.model_validate(payload), False
    except (ValidationError, ValueError) as exc:
        error_text = str(exc)
        logger.warning(
            "%s output failed schema validation, attempting repair: %s",
            agent_name,
            error_text,
        )

    try:
        schema = json.dumps(model_cls.model_json_schema())
        source = json.dumps(payload) if isinstance(payload, dict) else (raw_text or "(empty)")
        repair_prompt = REPAIR_PROMPT.format(raw=source, error=error_text, schema=schema)
        response = await invoke_llm([HumanMessage(content=repair_prompt)])
        repaired_text = response.content if isinstance(response.content, str) else str(response.content)
        repaired = parse_json_content(repaired_text)
        if not isinstance(repaired, dict):
            raise ValueError("repair output was not a JSON object")
        merged = {**(payload if isinstance(payload, dict) else {}), **repaired}
        return model_cls.model_validate(merged), True
    except Exception as exc:
        logger.warning(
            "%s repair attempt failed, degrading to unavailable: %s",
            agent_name,
            exc,
        )

    return model_cls.unavailable(error_text), True
