import base64
import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from tcad_agent.remote_protocol.models import SubmitJobPayload
from tcad_agent.remote_protocol.signing import (
    encode_private_key,
    encode_public_key,
    sign_submit_request,
)
from tcad_agent.sentaurus_runner.app import SentaurusRunnerSettings, create_app
from tcad_agent.sentaurus_runner.executor import ExecutorResult


class StubExecutor:
    def execute(self, job_dir: Path, *, timeout_seconds: float) -> ExecutorResult:
        del timeout_seconds
        (job_dir / "sdevice.log").write_text("ok\n")
        (job_dir / "sdevice.tdr").write_bytes(b"tdr")
        return ExecutorResult(
            status="completed",
            return_code=0,
            elapsed_seconds=0.1,
            error=None,
        )


def archive(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as bundle:
        for name, content in files.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            bundle.writestr(info, content)
    return stream.getvalue()


def request_for(
    private: Ed25519PrivateKey,
    bundle: bytes,
    *,
    version: str = "S-2024.03",
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
):
    now = datetime.now(UTC)
    payload = SubmitJobPayload(
        job_id=uuid4(),
        required_simulator_version=version,
        manifest_sha256=hashlib.sha256(bundle).hexdigest(),
        bundle_b64=base64.b64encode(bundle).decode(),
        issued_at=issued_at or now,
        expires_at=expires_at or now + timedelta(minutes=5),
    )
    return sign_submit_request(payload, encode_private_key(private))


@pytest.fixture
def configured(tmp_path: Path):
    private = Ed25519PrivateKey.generate()
    settings = SentaurusRunnerSettings(
        job_root=tmp_path / "jobs",
        executable=tmp_path / "licensed" / "sdevice",
        exact_version="S-2024.03",
        trusted_public_key=encode_public_key(private.public_key()),
        output_allowlist=("sdevice.log", "sdevice.tdr"),
        max_upload_bytes=4096,
    )
    client = TestClient(create_app(settings, executor=StubExecutor()))
    return client, private


def valid_bundle(*, expected_outputs: list[str] | None = None) -> bytes:
    manifest = {
        "backend": "sentaurus",
        "command_file": "sdevice.cmd",
        "expected_outputs": expected_outputs or ["sdevice.log", "sdevice.tdr"],
    }
    return archive(
        {
            "sdevice.cmd": b"Solve { Coupled { Poisson } }\n",
            "job-manifest.json": json.dumps(manifest).encode(),
        }
    )


def test_valid_job_can_be_retrieved(configured) -> None:
    client, private = configured
    request = request_for(private, valid_bundle())
    response = client.post("/v1/jobs", json=request.model_dump(mode="json"))
    assert response.status_code == 201, response.text
    job_id = response.json()["job_id"]
    result = client.get(f"/v1/jobs/{job_id}/result")
    assert result.status_code == 200
    assert base64.b64decode(result.json()["files_b64"]["sdevice.tdr"]) == b"tdr"


def test_wrong_backend_is_rejected(configured) -> None:
    client, private = configured
    body = request_for(private, valid_bundle()).model_dump(mode="json")
    body["backend"] = "devsim"
    assert client.post("/v1/jobs", json=body).status_code == 422


def test_version_mismatch_is_rejected(configured) -> None:
    client, private = configured
    request = request_for(private, valid_bundle(), version="S-2023.12")
    assert client.post("/v1/jobs", json=request.model_dump(mode="json")).status_code == 409


def test_expired_request_is_rejected(configured) -> None:
    client, private = configured
    now = datetime.now(UTC)
    request = request_for(
        private,
        valid_bundle(),
        issued_at=now - timedelta(minutes=10),
        expires_at=now - timedelta(minutes=5),
    )
    assert client.post("/v1/jobs", json=request.model_dump(mode="json")).status_code == 401


def test_replayed_job_id_is_rejected(configured) -> None:
    client, private = configured
    request = request_for(private, valid_bundle())
    body = request.model_dump(mode="json")
    assert client.post("/v1/jobs", json=body).status_code == 201
    assert client.post("/v1/jobs", json=body).status_code == 409


def test_archive_path_traversal_is_rejected(configured) -> None:
    client, private = configured
    bundle = archive({"../escape": b"bad", "job-manifest.json": b"{}"})
    request = request_for(private, bundle)
    assert client.post("/v1/jobs", json=request.model_dump(mode="json")).status_code == 400


def test_oversized_upload_is_rejected(configured) -> None:
    client, private = configured
    bundle = archive({"huge.bin": b"x" * 5000})
    request = request_for(private, bundle)
    assert client.post("/v1/jobs", json=request.model_dump(mode="json")).status_code == 413


def test_hash_mismatch_is_rejected(configured) -> None:
    client, private = configured
    request = request_for(private, valid_bundle())
    request = request.model_copy(update={"bundle_b64": base64.b64encode(b"changed").decode()})
    assert client.post("/v1/jobs", json=request.model_dump(mode="json")).status_code == 400


def test_untrusted_signature_is_rejected(configured) -> None:
    client, _private = configured
    outsider = Ed25519PrivateKey.generate()
    request = request_for(outsider, valid_bundle())
    assert client.post("/v1/jobs", json=request.model_dump(mode="json")).status_code == 401


def test_non_allowlisted_output_is_rejected(configured) -> None:
    client, private = configured
    bundle = valid_bundle(expected_outputs=["sdevice.log", "secret.txt"])
    request = request_for(private, bundle)
    assert client.post("/v1/jobs", json=request.model_dump(mode="json")).status_code == 400
