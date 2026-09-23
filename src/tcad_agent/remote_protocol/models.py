"""Typed wire contracts for the licensed Sentaurus runner."""

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from tcad_agent.domain.models import StrictModel


class SubmitJobPayload(StrictModel):
    protocol_version: Literal["1.0"] = "1.0"
    job_id: UUID
    backend: Literal["sentaurus"] = "sentaurus"
    required_simulator_version: str = Field(min_length=1, max_length=128)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundle_b64: str = Field(min_length=1)
    issued_at: datetime
    expires_at: datetime

    @field_validator("issued_at", "expires_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("protocol timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def require_expiration_after_issue(self) -> Self:
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be later than issued_at")
        return self


class SubmitJobRequest(SubmitJobPayload):
    signature_b64: str = Field(min_length=1)


class RemoteJobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class RemoteJobHandle(StrictModel):
    job_id: UUID
    state: RemoteJobState


class RemoteJobStatus(StrictModel):
    job_id: UUID
    state: RemoteJobState
    error: str | None = None


class RemoteJobResult(StrictModel):
    job_id: UUID
    status: Literal["completed", "execution_failed", "timed_out", "malformed_result"]
    return_code: int | None
    elapsed_seconds: float = Field(ge=0)
    files_b64: dict[str, str]
    files_sha256: dict[str, str]
    error: str | None = None
