from pathlib import Path

import pytest

from tcad_agent.adapters.registry import BackendAdapterUnavailable, get_backend


def test_devsim_backend_binding_owns_adapter_and_runner() -> None:
    binding = get_backend("devsim")

    assert binding.adapter.manifest.backend == "devsim"


def test_sentaurus_binding_is_installed_but_execution_is_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "TCAD_SENTAURUS_ENDPOINT",
        "TCAD_SENTAURUS_SIGNING_PRIVATE_KEY",
        "TCAD_SENTAURUS_TRUSTED_PUBLIC_KEY",
        "TCAD_SENTAURUS_VERSION",
    ):
        monkeypatch.delenv(name, raising=False)
    binding = get_backend("sentaurus")
    assert binding.adapter.manifest.backend == "sentaurus"
    assert not binding.runner.config.configured


def test_unknown_backend_refuses_explicitly() -> None:
    with pytest.raises(BackendAdapterUnavailable, match="unknown"):
        get_backend("unknown")


def test_researcher_interfaces_do_not_import_devsim_adapter_directly() -> None:
    project = Path(__file__).parents[3]
    for relative in ("src/tcad_agent/cli.py", "src/tcad_agent/agent/tools.py"):
        source = (project / relative).read_text()
        assert "DevsimAdapter" not in source
        assert 'backend != "devsim"' not in source
