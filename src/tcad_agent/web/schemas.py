"""HTTP request contracts for the local researcher interface."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tcad_agent.control.models import ClarificationAnswer


class WebRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateResearchRequest(WebRequest):
    prompt: str = Field(min_length=1, max_length=100_000)
    backend: Literal["devsim", "sentaurus"] = "devsim"


class AnswerRequest(WebRequest):
    answers: tuple[ClarificationAnswer, ...]


class ApprovalRequest(WebRequest):
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
