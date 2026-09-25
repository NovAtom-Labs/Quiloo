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
