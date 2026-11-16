"""Pydantic models for LLM-produced agent outputs.

These are distinct from app.core.schemas, which validates API request/response
bodies. Models here are validated against raw LLM JSON via
app.core.parse.validate_with_repair, with bounded retry/repair and an explicit
"unavailable" fallback instead of silent None fields.
"""

from typing import Any, Literal, Optional, Self

from pydantic import BaseModel, Field


class LLMOutputModel(BaseModel):
    """Base class for validated LLM outputs; tracks parse/repair provenance."""

    generation_status: Literal["ok", "repaired", "unavailable"] = "ok"

    @classmethod
    def unavailable(cls, reason: str) -> Self:
        raise NotImplementedError


class Coordinates(BaseModel):
    lat: float
    lon: float


class DestinationAgentOutput(LLMOutputModel):
    attractions: list[str] = Field(default_factory=list)
    coordinates: Optional[Coordinates] = None
    nominatim_results: list[dict[str, Any]] = Field(default_factory=list)
    weather: Optional[dict[str, Any]] = None
    packing_tips: Optional[str] = None
    notes: Optional[str] = None
    visa_safety_cuisine: Optional[str] = None
    tool_errors: list[str] = Field(default_factory=list)

    @classmethod
    def unavailable(cls, reason: str) -> "DestinationAgentOutput":
        return cls(
            notes="Destination research could not be generated due to a parsing error.",
            tool_errors=[reason],
            generation_status="unavailable",
        )


class ItineraryDay(BaseModel):
    day: Optional[int] = None
    morning: Optional[str] = None
    afternoon: Optional[str] = None
    evening: Optional[str] = None
    notes: Optional[str] = None


class ItineraryAgentOutput(LLMOutputModel):
    days: list[ItineraryDay] = Field(default_factory=list)
    travel_legs: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def unavailable(cls, reason: str) -> "ItineraryAgentOutput":
        return cls(
            warnings=[f"Itinerary could not be generated due to a parsing error: {reason}"],
            generation_status="unavailable",
        )


class AccommodationOption(BaseModel):
    title: Optional[str] = None
    snippet: Optional[str] = None
    href: Optional[str] = None
    stated_price_or_null: Optional[str] = None
    source: Optional[str] = None


class AccommodationAgentOutput(LLMOutputModel):
    options: list[AccommodationOption] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def unavailable(cls, reason: str) -> "AccommodationAgentOutput":
        return cls(
            warnings=[f"Accommodation options could not be generated due to a parsing error: {reason}"],
            generation_status="unavailable",
        )


class TransportOption(BaseModel):
    title: Optional[str] = None
    snippet: Optional[str] = None
    href: Optional[str] = None
    mode_if_stated: Optional[str] = None
    stated_price_or_null: Optional[str] = None
    source: Optional[str] = None


class TransportAgentOutput(LLMOutputModel):
    options: list[TransportOption] = Field(default_factory=list)
    query_used: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def unavailable(cls, reason: str) -> "TransportAgentOutput":
        return cls(
            warnings=[f"Transport options could not be generated due to a parsing error: {reason}"],
            generation_status="unavailable",
        )


class AggregatorPlanOutput(LLMOutputModel):
    summary: str
    itinerary: Optional[dict[str, Any]] = None
    accommodation: list[dict[str, Any]] = Field(default_factory=list)
    transport: list[dict[str, Any]] = Field(default_factory=list)
    budget_notes: str
    tips: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def unavailable(cls, reason: str) -> "AggregatorPlanOutput":
        return cls(
            summary="Summary could not be generated due to a parsing error.",
            budget_notes="Budget notes could not be generated due to a parsing error.",
            tips=["Tips could not be generated due to a parsing error."],
            warnings=[f"Aggregator output unavailable: {reason}"],
            generation_status="unavailable",
        )
