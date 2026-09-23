import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tcad_agent.remote_protocol.signing import encode_private_key, encode_public_key
from tcad_agent.runners.models import CompiledJob, RunBudget
from tcad_agent.runners.remote import (
    RemoteRunnerConfig,
    RemoteSentaurusRunner,
)

EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
TDR_SHA256 = "50dc112448d0f42a9e1d9a2075ebe73d0a23bbc8020eeb1b3e34b34f5cdb03c9"


def compiled_job(tmp_path: Path) -> CompiledJob:
    tmp_path.mkdir(parents=True, exist_ok=True)
    command = tmp_path / "sdevice.cmd"
    command.write_text("Solve { Coupled { Poisson } }\n")
    manifest = tmp_path / "job-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "backend": "sentaurus",
                "expected_outputs": ["sdevice.log", "sdevice.tdr"],
            }
        )
    )
    return CompiledJob(
        backend="sentaurus",
        entrypoint=command,
        input_files=(command, manifest),
        input_digest="a" * 64,
        runtime_digest="b" * 64,
        compiler_version="0.1.0",
    )


def test_http_client_submits_signed_bundle_and_materializes_result(tmp_path: Path) -> None:
    private = Ed25519PrivateKey.generate()
    seen: dict[str, object] = {}
    job_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            body = json.loads(request.content)
            seen.update(body)
            return httpx.Response(
                201,
                json={"job_id": str(job_id), "state": "completed"},
            )
        if request.url.path.endswith("/status"):
            return httpx.Response(
                200,
                json={"job_id": str(job_id), "state": "completed", "error": None},
            )
        return httpx.Response(
            200,
            json={
                "job_id": str(job_id),
                "status": "completed",
                "return_code": 0,
                "elapsed_seconds": 0.1,
                "files_b64": {
                    "runner.stdout.log": "",
                    "runner.stderr.log": "",
                    "sdevice.tdr": "dGRy",
                },
                "files_sha256": {
                    "runner.stdout.log": EMPTY_SHA256,
                    "runner.stderr.log": EMPTY_SHA256,
                    "sdevice.tdr": TDR_SHA256,
                },
                "error": None,
            },
        )

    runner = RemoteSentaurusRunner(
        RemoteRunnerConfig(
            endpoint="https://runner.example.test",
            signing_private_key=encode_private_key(private),
            trusted_public_key=encode_public_key(private.public_key()),
            sentaurus_version="S-2024.03",
        ),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        clock=lambda: datetime(2026, 9, 23, tzinfo=UTC),
        uuid_factory=lambda: job_id,
    )
    result = runner.run(compiled_job(tmp_path), RunBudget(seconds=30))

    assert result.status == "completed"
    assert result.result_path is not None
    assert result.result_path.read_bytes() == b"tdr"
    assert seen["required_simulator_version"] == "S-2024.03"
    assert seen["timeout_seconds"] == 30
    assert seen["signature_b64"]
    assert seen["bundle_b64"]


def test_remote_runner_rejects_artifact_outside_workspace(tmp_path: Path) -> None:
    job = compiled_job(tmp_path / "job")
    outside = tmp_path / "outside.txt"
    outside.write_text("no")
    job = job.model_copy(update={"input_files": (*job.input_files, outside)})
    try:
        RemoteSentaurusRunner.verify_workspace(job, job.entrypoint.parent)
    except ValueError as exc:
        assert "outside" in str(exc)
    else:
        raise AssertionError("outside input was accepted")
