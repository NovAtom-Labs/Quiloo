"""Research request and lifecycle state models."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, JsonValue

from tcad_agent.domain.models import StrictModel


class RequestState(StrEnum):
    REQUESTED = "requested"
    NEEDS_CLARIFICATION = "needs_clarification"
    SPEC_DRAFTED = "spec_drafted"
    SPEC_VALIDATED = "spec_validated"
    USER_CONFIRMATION_REQUIRED = "user_confirmation_required"
    COMPILED = "compiled"
    RUNNING = "running"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchRequest(StrictModel):
    prompt: str = Field(min_length=1, max_length=100_000)


class RequestRecord(StrictModel):
    id: UUID
    request: ResearchRequest
    state: RequestState
    revision: int = Field(ge=0)
    data: dict[str, JsonValue]
    created_at: datetime
    updated_at: datetime
