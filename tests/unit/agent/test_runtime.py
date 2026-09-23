from pathlib import Path

from tcad_agent.agent.runtime import build_runtime

ROOT = Path(__file__).parents[3]


def test_runtime_defaults_to_pilot_bedrock_model(monkeypatch) -> None:
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("TCAD_REASONING_EFFORT", raising=False)

    profile = build_runtime(ROOT)

    assert profile.model == "bedrock/global.anthropic.claude-sonnet-5"
    assert profile.reasoning_effort == "medium"


def test_runtime_preserves_model_override_for_future_routing(monkeypatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "bedrock/openai.gpt-5.6-sol")
    monkeypatch.setenv("TCAD_REASONING_EFFORT", "high")

    profile = build_runtime(ROOT)

    assert profile.model == "bedrock/openai.gpt-5.6-sol"
    assert profile.reasoning_effort == "high"
