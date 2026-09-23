import json

from typer.testing import CliRunner

from tcad_agent.cli import app

runner = CliRunner()


def test_cli_runs_example_to_completed_bundle(tmp_path) -> None:
    result = runner.invoke(
        app,
        [
            "run",
            "examples/pn-junction.yaml",
            "--backend",
            "devsim",
            "--approve",
            "--output",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    manifest_path = next(tmp_path.glob("*/manifest.json"))
    manifest = json.loads(manifest_path.read_text())
    assert manifest["state"] == "completed"
    assert (manifest_path.parent / "report.md").is_file()
