import json
from pathlib import Path

from tcad_agent.bundles.models import BundleInputs
from tcad_agent.bundles.writer import BundleWriter
from tcad_agent.domain.models import ExperimentSpec
from tcad_agent.results.models import BiasPoint, CanonicalResult
from tcad_agent.runners.models import CompiledJob, NativeRunResult
from tcad_agent.validation.engine import ValidationEngine


def bundle_inputs(tmp_path: Path, valid_spec: ExperimentSpec) -> BundleInputs:
    compiled = tmp_path / "source-compiled"
    compiled.mkdir()
    input_path = compiled / "input.json"
    runtime_path = compiled / "run_devsim.py"
    stdout_path = compiled / "stdout.log"
    stderr_path = compiled / "stderr.log"
    native_path = compiled / "native_result.json"
    input_path.write_text("{}")
    runtime_path.write_text("# reviewed runtime\n")
    stdout_path.write_text("solver completed\n")
    stderr_path.write_text("")
    native_path.write_text("{}")
    job = CompiledJob(
        backend="devsim",
        entrypoint=runtime_path,
        input_files=(input_path, runtime_path),
        input_digest="a" * 64,
        runtime_digest="b" * 64,
        compiler_version="0.1.0",
    )
    native = NativeRunResult(
        backend="devsim",
        status="completed",
        return_code=0,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        result_path=native_path,
        elapsed_seconds=0.25,
    )
    result = CanonicalResult(
        backend="devsim",
        simulator_version="2.9.1",
        status="completed",
        terminals=("anode", "cathode"),
        bias_points=(
            BiasPoint(
                bias_v=0.1,
                converged=True,
                terminal_currents_a_per_m2={"anode": 1.0, "cathode": -1.0},
            ),
        ),
    )
    validation = ValidationEngine().validate(result)
    return BundleInputs(
        run_id="run-0001",
        spec=valid_spec,
        job=job,
        native=native,
        result=result,
        validation=validation,
    )


def test_bundle_manifest_hashes_every_artifact_and_report_uses_structured_values(
    tmp_path: Path, valid_spec: ExperimentSpec
) -> None:
    bundle = BundleWriter(tmp_path / "bundles").write(bundle_inputs(tmp_path, valid_spec))
    manifest = json.loads((bundle.root / "manifest.json").read_text())
    assert manifest["state"] == "completed"
    assert set(manifest["artifacts"]) >= {
        "experiment.json",
        "compiled/input.json",
        "logs/stdout.log",
        "results/canonical.json",
        "validation/report.json",
        "report.md",
    }
    assert all(item["sha256"] for item in manifest["artifacts"].values())
    assert "1.000000e+00 A/m^2" in (bundle.root / "report.md").read_text()
