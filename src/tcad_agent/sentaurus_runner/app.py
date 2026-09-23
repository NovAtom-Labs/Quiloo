"""Authenticated reference API for a licensed Sentaurus execution host."""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import shutil
import stat
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal, Protocol
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import Field

from tcad_agent.domain.models import StrictModel
from tcad_agent.remote_protocol.models import (
    RemoteJobHandle,
    RemoteJobResult,
    RemoteJobState,
    RemoteJobStatus,
    SubmitJobRequest,
)
from tcad_agent.remote_protocol.signing import (
    SignatureVerificationError,
    verify_submit_request,
)
from tcad_agent.sentaurus_runner.executor import ExecutorResult, SentaurusExecutor


class SentaurusRunnerSettings(StrictModel):
    job_root: Path
    executable: Path | None = None
    exact_version: str | None = None
    trusted_public_key: str | None = None
    output_allowlist: tuple[str, ...] = (
        "sdevice.log",
        "sdevice.plt",
        "sdevice.tdr",
    )
    max_upload_bytes: int = Field(default=16 * 1024 * 1024, gt=0)
    max_files: int = Field(default=64, gt=0, le=1024)
    execution_timeout_seconds: float = Field(default=900, gt=0, le=3600)

    @property
    def configured(self) -> bool:
        return bool(self.executable and self.exact_version and self.trusted_public_key)


class JobExecutor(Protocol):
    def execute(self, job_dir: Path, *, timeout_seconds: float) -> ExecutorResult: ...


class RunnerManifest(StrictModel):
    backend: Literal["sentaurus"]
    command_file: Literal["sdevice.cmd"] = "sdevice.cmd"
    expected_outputs: tuple[str, ...]


class _StoredJob:
    def __init__(
        self,
        *,
        job_dir: Path,
        expected_outputs: tuple[str, ...],
        result: ExecutorResult,
    ) -> None:
        self.job_dir = job_dir
        self.expected_outputs = expected_outputs
        self.result = result


def _decode_bundle(request: SubmitJobRequest, maximum: int) -> bytes:
    try:
        bundle = base64.b64decode(request.bundle_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(status_code=400, detail="bundle is not valid base64") from exc
    if len(bundle) > maximum:
        raise HTTPException(status_code=413, detail="bundle exceeds the upload limit")
    if hashlib.sha256(bundle).hexdigest() != request.manifest_sha256:
        raise HTTPException(status_code=400, detail="bundle digest does not match")
    return bundle


def _safe_extract(bundle: bytes, target: Path, settings: SentaurusRunnerSettings) -> set[str]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(bundle))
    except (zipfile.BadZipFile, OSError) as exc:
        raise HTTPException(status_code=400, detail="bundle is not a valid ZIP archive") from exc
    with archive:
        members = archive.infolist()
        if len(members) > settings.max_files:
            raise HTTPException(status_code=413, detail="bundle contains too many files")
        if sum(member.file_size for member in members) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="expanded bundle exceeds the limit")
        names: set[str] = set()
        for member in members:
            path = PurePosixPath(member.filename)
            mode = member.external_attr >> 16
            if (
                not member.filename
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in member.filename
                or len(path.parts) != 1
                or stat.S_ISLNK(mode)
                or member.is_dir()
            ):
                raise HTTPException(status_code=400, detail="unsafe archive path")
            if member.filename in names:
                raise HTTPException(status_code=400, detail="duplicate archive path")
            names.add(member.filename)
            destination = (target / member.filename).resolve()
            if not destination.is_relative_to(target.resolve()):
                raise HTTPException(status_code=400, detail="unsafe archive path")
            destination.write_bytes(archive.read(member))
    return names


def create_app(
    settings: SentaurusRunnerSettings,
    *,
    executor: JobExecutor | None = None,
) -> FastAPI:
    app = FastAPI(title="NovAtom Licensed Sentaurus Runner")
    jobs: dict[UUID, _StoredJob] = {}
    runner = executor
    if runner is None and settings.executable is not None:
        runner = SentaurusExecutor(settings.executable)

    @app.get("/health")
    def health() -> dict[str, str | bool | None]:
        return {
            "status": "ok",
            "configured": settings.configured,
            "sentaurus_version": settings.exact_version,
        }

    @app.post("/v1/jobs", status_code=201)
    def submit(request: SubmitJobRequest) -> RemoteJobHandle:
        if not settings.configured or runner is None:
            raise HTTPException(status_code=503, detail="runner is not configured")
        assert settings.trusted_public_key is not None
        assert settings.exact_version is not None
        now = datetime.now(UTC)
        if request.issued_at > now or request.expires_at < now:
            raise HTTPException(status_code=401, detail="request is outside its validity window")
        try:
            verify_submit_request(request, settings.trusted_public_key)
        except SignatureVerificationError as exc:
            raise HTTPException(status_code=401, detail="signature is not trusted") from exc
        if request.required_simulator_version != settings.exact_version:
            raise HTTPException(status_code=409, detail="simulator version does not match")
        if request.job_id in jobs:
            raise HTTPException(status_code=409, detail="job ID has already been used")
        bundle = _decode_bundle(request, settings.max_upload_bytes)

        settings.job_root.mkdir(parents=True, exist_ok=True)
        job_dir = (settings.job_root / str(request.job_id)).resolve()
        if not job_dir.is_relative_to(settings.job_root.resolve()):
            raise HTTPException(status_code=400, detail="invalid job ID")
        job_dir.mkdir(mode=0o700, exist_ok=False)
        try:
            input_names = _safe_extract(bundle, job_dir, settings)
            manifest_path = job_dir / "job-manifest.json"
            if not manifest_path.is_file():
                raise HTTPException(status_code=400, detail="job manifest is missing")
            try:
                raw_manifest = json.loads(manifest_path.read_text())
                manifest = RunnerManifest.model_validate(
                    {
                        "backend": raw_manifest.get("backend"),
                        "command_file": raw_manifest.get("command_file", "sdevice.cmd"),
                        "expected_outputs": raw_manifest.get("expected_outputs"),
                    }
                )
            except (json.JSONDecodeError, AttributeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail="job manifest is invalid") from exc
            if not (job_dir / manifest.command_file).is_file():
                raise HTTPException(status_code=400, detail="command file is missing")
            if set(manifest.expected_outputs) - set(settings.output_allowlist):
                raise HTTPException(status_code=400, detail="requested output is not allowlisted")

            execution = runner.execute(job_dir, timeout_seconds=settings.execution_timeout_seconds)
            allowed_files = (
                input_names
                | set(manifest.expected_outputs)
                | {
                    "runner.stdout.log",
                    "runner.stderr.log",
                }
            )
            produced = {path.name for path in job_dir.iterdir() if path.is_file()}
            if produced - allowed_files:
                raise HTTPException(
                    status_code=400, detail="runner produced a non-allowlisted file"
                )
            jobs[request.job_id] = _StoredJob(
                job_dir=job_dir,
                expected_outputs=manifest.expected_outputs,
                result=execution,
            )
        except Exception:
            if request.job_id not in jobs:
                shutil.rmtree(job_dir, ignore_errors=True)
            raise
        state = {
            "completed": RemoteJobState.COMPLETED,
            "execution_failed": RemoteJobState.FAILED,
            "timed_out": RemoteJobState.TIMED_OUT,
        }[execution.status]
        return RemoteJobHandle(job_id=request.job_id, state=state)

    @app.get("/v1/jobs/{job_id}/status")
    def status(job_id: UUID) -> RemoteJobStatus:
        stored = jobs.get(job_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="job was not found")
        state = {
            "completed": RemoteJobState.COMPLETED,
            "execution_failed": RemoteJobState.FAILED,
            "timed_out": RemoteJobState.TIMED_OUT,
        }[stored.result.status]
        return RemoteJobStatus(job_id=job_id, state=state, error=stored.result.error)

    @app.get("/v1/jobs/{job_id}/result")
    def result(job_id: UUID) -> RemoteJobResult:
        stored = jobs.get(job_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="job was not found")
        names = (*stored.expected_outputs, "runner.stdout.log", "runner.stderr.log")
        files = {
            name: (stored.job_dir / name).read_bytes()
            for name in names
            if (stored.job_dir / name).is_file()
        }
        result_status: Literal["completed", "execution_failed", "timed_out", "malformed_result"] = (
            stored.result.status
        )
        return RemoteJobResult(
            job_id=job_id,
            status=result_status,
            return_code=stored.result.return_code,
            elapsed_seconds=stored.result.elapsed_seconds,
            files_b64={name: base64.b64encode(data).decode() for name, data in files.items()},
            files_sha256={name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
            error=stored.result.error,
        )

    return app
