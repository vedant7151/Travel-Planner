from datetime import date
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TripRequest(BaseModel):
    user_id: UUID
    origin: Optional[str] = Field(default=None, max_length=200)
    destination: str = Field(..., min_length=1, max_length=200)
    start_date: str
    end_date: str
    budget_usd: float = Field(..., ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    travellers: int = Field(default=1, ge=1, le=20)
    preferences: dict[str, Any] = Field(default_factory=dict)

    @field_validator("start_date", "end_date")
    @classmethod
    def _iso_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Dates must be ISO 8601 (YYYY-MM-DD)") from exc
        return value

    @field_validator("destination")
    @classmethod
    def _destination(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("destination is required")
        return stripped

    @field_validator("currency")
    @classmethod
    def _currency(cls, value: str) -> str:
        code = value.strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise ValueError("currency must be a 3-letter ISO 4217 code (e.g. USD, INR, EUR)")
        return code

    @field_validator("origin")
    @classmethod
    def _origin(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None


class PreferencesUpdate(BaseModel):
    preferences: dict[str, Any]


class TripResponse(BaseModel):
    trip_id: str
    status: str
    user_id: Optional[UUID] = None
    request: Optional[dict[str, Any]] = None
    itinerary: Optional[dict[str, Any]] = None
    accommodation: Optional[list] = None
    transport: Optional[list] = None
    total_estimated_cost: Optional[float] = None
    currency: Optional[str] = None
    map_url: Optional[str] = None
    image_url: Optional[str] = None
    places: Optional[list] = None
    final_plan: Optional[dict[str, Any]] = None
    degraded_sections: Optional[list[str]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None


class TripStatus(BaseModel):
    trip_id: str
    status: str
    error: Optional[str] = None
