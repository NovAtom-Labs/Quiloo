from pathlib import Path

import yaml

from tcad_agent.agent.tools import TcadDomainAction, TcadDomainExecutor, build_tools

ROOT = Path(__file__).parents[3]


def valid_spec_payload() -> dict:
    return yaml.safe_load((ROOT / "examples" / "pn-junction.yaml").read_text())


def test_run_tool_requires_validated_plan(tmp_path: Path) -> None:
    tools = build_tools(tmp_path)
    response = tools.run_experiment({"spec_path": "spec.yaml", "backend": "devsim"})
    assert response.status == "refused"
    assert response.code == "approval_required"


def test_sentaurus_compiles_without_configured_remote(tmp_path: Path) -> None:
    response = build_tools(tmp_path).compile_experiment(
        valid_spec_payload(), backend="sentaurus"
    )
    assert response.status == "ok"
    assert response.code == "compiled"
    assert response.data["job"]["backend"] == "sentaurus"


def test_tcad_executor_returns_llm_visible_refusal_for_missing_payload(
    tmp_path: Path,
) -> None:
    observation = TcadDomainExecutor(tmp_path)(
        TcadDomainAction(operation="validate_spec")
    )

    assert observation.status == "refused"
    assert observation.code == "invalid_spec"
    assert observation.content
    assert '"code": "invalid_spec"' in observation.text
