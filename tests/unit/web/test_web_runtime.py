import socket

from tcad_agent.web.launcher import _select_port
from tcad_agent.web.runtime import runtime_fingerprint


def test_runtime_fingerprint_excludes_bedrock_secret(monkeypatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "bedrock/global.anthropic.claude-sonnet-4-6")
    monkeypatch.setenv("AWS_REGION_NAME", "ap-south-1")
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "first-secret")
    first = runtime_fingerprint()
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "second-secret")
    assert runtime_fingerprint() == first


def test_runtime_fingerprint_changes_with_model(monkeypatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "bedrock/model-a")
    first = runtime_fingerprint()
    monkeypatch.setenv("LLM_MODEL", "bedrock/model-b")
    assert runtime_fingerprint() != first


def test_select_port_uses_next_free_port_when_default_is_occupied() -> None:
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        port = occupied.getsockname()[1]
        selected, reused = _select_port(port, expected_fingerprint="new-runtime")
    assert selected != port
    assert reused is False
