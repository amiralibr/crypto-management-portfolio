"""Common API response and error schemas for MVP-0."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standardized error response schema."""

    code: str
    message: str
    request_id: str
    details: dict[str, Any] = Field(default_factory=dict)
