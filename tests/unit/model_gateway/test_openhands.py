import json
from types import SimpleNamespace

import pytest
from openhands.sdk import TextContent

from tcad_agent.control.models import ResearchRequest
from tcad_agent.model_gateway.base import AgentContextPacket, AgentProposal, ScriptedModelGateway
from tcad_agent.model_gateway.openhands import (
    ModelConfigurationError,
    OpenHandsBedrockGateway,
)


class FakeLLM:
    def __init__(self, response: str | Exception) -> None:
        self.response = response

    def completion(self, messages, tools=None):
        if isinstance(self.response, Exception):
            raise self.response
        return SimpleNamespace(
            message=SimpleNamespace(content=[TextContent(text=self.response)])
        )


def test_scripted_gateway_returns_typed_proposals_in_order() -> None:
    first = AgentProposal(kind="clarification", questions=())
    second = AgentProposal(kind="refusal", message="unsupported")
    gateway = ScriptedModelGateway((first, second))
    request = ResearchRequest(prompt="simulate")
    context = AgentContextPacket()
    assert gateway.propose(request, context) == first
    assert gateway.propose(request, context) == second


def test_openhands_gateway_parses_structured_proposal() -> None:
    payload = {"kind": "refusal", "questions": [], "message": "unsupported"}
    gateway = OpenHandsBedrockGateway(FakeLLM(json.dumps(payload)))
    proposal = gateway.propose(ResearchRequest(prompt="simulate"), AgentContextPacket())
    assert proposal == AgentProposal.model_validate(payload)


def test_openhands_gateway_redacts_provider_error_secrets() -> None:
    secret = "ABSK-secret-value"
    gateway = OpenHandsBedrockGateway(
        FakeLLM(RuntimeError(f"authentication rejected token {secret}"))
    )
    with pytest.raises(ModelConfigurationError) as caught:
        gateway.propose(ResearchRequest(prompt="simulate"), AgentContextPacket())
    assert secret not in str(caught.value)


def test_environment_factory_requires_bedrock_credential(monkeypatch) -> None:
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
    with pytest.raises(ModelConfigurationError, match="AWS_BEARER_TOKEN_BEDROCK"):
        OpenHandsBedrockGateway.from_environment()
