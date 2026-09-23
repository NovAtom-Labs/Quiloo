from pathlib import Path

import pytest

from tcad_agent.adapters.registry import BackendAdapterUnavailable, get_backend


def test_devsim_backend_binding_owns_adapter_and_runner() -> None:
    binding = get_backend("devsim")

    assert binding.adapter.manifest.backend == "devsim"


def test_uninstalled_sentaurus_adapter_refuses_explicitly() -> None:
    with pytest.raises(BackendAdapterUnavailable, match="sentaurus"):
        get_backend("sentaurus")


def test_researcher_interfaces_do_not_import_devsim_adapter_directly() -> None:
    project = Path(__file__).parents[3]
    for relative in ("src/tcad_agent/cli.py", "src/tcad_agent/agent/tools.py"):
        source = (project / relative).read_text()
        assert "DevsimAdapter" not in source
        assert 'backend != "devsim"' not in source
