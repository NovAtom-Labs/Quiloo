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


class ClarificationQuestion(StrictModel):
    field: str = Field(min_length=1)
    prompt: str = Field(min_length=1)


class ClarificationAnswer(StrictModel):
    field: str = Field(min_length=1)
    value: str = Field(min_length=1)


class RequestRecord(StrictModel):
    id: UUID
    request: ResearchRequest
    state: RequestState
    revision: int = Field(ge=0)
    data: dict[str, JsonValue]
    created_at: datetime
    updated_at: datetime


class RequestView(StrictModel):
    id: UUID
    prompt: str
    state: RequestState
    revision: int
    backend: str
    clarification_answers: dict[str, str] = Field(default_factory=dict)
    questions: tuple[ClarificationQuestion, ...] = ()
    plan_digest: str | None = None
    plan: dict[str, JsonValue] | None = None
    spec: dict[str, JsonValue] | None = None
    validation: dict[str, JsonValue] | None = None
    bundle_path: str | None = None
    warnings: tuple[str, ...] = ()
    error_code: str | None = None
    error_message: str | None = None
