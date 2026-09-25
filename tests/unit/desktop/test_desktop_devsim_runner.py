from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tcad_agent.desktop.devsim_runner import (
    execute_manifest,
    main,
    write_compiled_job_manifest,
)
from tcad_agent.runners.models import CompiledJob, RunBudget


def _manifest(tmp_path: Path) -> tuple[Path, str]:
    runtime = tmp_path / "run_devsim.py"
    runtime.write_text("# reviewed runtime\n")
    payload = tmp_path / "input.json"
    payload.write_text('{"schema_version": "1.0"}\n')
    runtime_digest = hashlib.sha256(runtime.read_bytes()).hexdigest()
    input_digest = hashlib.sha256(payload.read_bytes()).hexdigest()
    manifest = tmp_path / "compiled-job.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "backend": "devsim",
                "job_root": str(tmp_path),
                "entrypoint": runtime.name,
                "arguments": [payload.name],
                "input_files": [payload.name, runtime.name],
                "input_digest": input_digest,
                "runtime_digest": runtime_digest,
                "budget_seconds": 30.0,
            }
        )
    )
    return manifest, runtime_digest


def test_execute_manifest_invokes_fixed_runtime_contract(tmp_path: Path) -> None:
    manifest, digest = _manifest(tmp_path)
    seen: dict[str, object] = {}

    def fixed_runtime() -> int:
        import sys

        seen["cwd"] = Path.cwd()
        seen["argv"] = list(sys.argv)
        return 0

    assert (
        execute_manifest(
            manifest,
            runtime_main=fixed_runtime,
            trusted_runtime_digest=digest,
        )
        == 0
    )
    assert seen == {
        "cwd": tmp_path,
        "argv": [str(tmp_path / "run_devsim.py"), str(tmp_path / "input.json")],
    }


def test_execute_manifest_rejects_paths_outside_job_root(tmp_path: Path) -> None:
    root = tmp_path / "job"
    root.mkdir()
    manifest, digest = _manifest(root)
    data = json.loads(manifest.read_text())
    data["entrypoint"] = "../outside.py"
    manifest.write_text(json.dumps(data))

    with pytest.raises(ValueError, match="inside the compiled job root"):
        execute_manifest(
            manifest,
            runtime_main=lambda: 0,
            trusted_runtime_digest=digest,
        )


def test_main_returns_sanitized_failure_for_malformed_job(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = tmp_path / "contains-secret-name.json"
    manifest.write_text("not-json-secret-value")

    assert main([str(manifest)]) == 2
    stderr = capsys.readouterr().err
    assert stderr == "Agent Kronig rejected an invalid compiled DEVSIM job.\n"
    assert "secret" not in stderr


def test_manifest_writer_refuses_compiled_inputs_outside_workspace(
    tmp_path: Path,
) -> None:
    root = tmp_path / "job"
    root.mkdir()
    entrypoint = root / "run_devsim.py"
    entrypoint.write_text("# runtime\n")
    outside = tmp_path / "input.json"
    outside.write_text("{}")
    job = CompiledJob(
        backend="devsim",
        entrypoint=entrypoint,
        arguments=("input.json",),
        input_files=(outside, entrypoint),
        input_digest=hashlib.sha256(outside.read_bytes()).hexdigest(),
        runtime_digest=hashlib.sha256(entrypoint.read_bytes()).hexdigest(),
        compiler_version="0.1.0",
    )

    with pytest.raises(ValueError, match="inside its compiled workspace"):
        write_compiled_job_manifest(job, RunBudget(seconds=30))
