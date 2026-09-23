from pathlib import Path

import yaml

from tcad_agent.agent.tools import build_tools

ROOT = Path(__file__).parents[3]


def valid_spec_payload() -> dict:
    return yaml.safe_load((ROOT / "examples" / "pn-junction.yaml").read_text())


def test_run_tool_requires_validated_plan(tmp_path: Path) -> None:
    tools = build_tools(tmp_path)
    response = tools.run_experiment({"spec_path": "spec.yaml", "backend": "devsim"})
    assert response.status == "refused"
    assert response.code == "approval_required"


def test_sentaurus_run_refuses_without_configured_remote(tmp_path: Path) -> None:
    response = build_tools(tmp_path).compile_experiment(
        valid_spec_payload(), backend="sentaurus"
    )
    assert response.status == "refused"
    assert response.code == "backend_unconfigured"
